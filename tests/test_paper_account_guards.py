from __future__ import annotations

import json
from pathlib import Path

import pytest

from week_trader.brokers.alpaca_paper import build_alpaca_order_body
from week_trader.paper_account_guards import (
    PaperAccountGuardError,
    assert_account_halt_absent,
    build_client_order_id,
    enforce_shared_account_guards,
    normalize_guard_symbol,
    resolve_symbol_owner,
)
from week_trader.paper_order import PaperOrderError, paper_order


def test_normalize_guard_symbol_btc_aliases() -> None:
    assert normalize_guard_symbol("BTC/USD") == "BTCUSD"
    assert normalize_guard_symbol("btcusd") == "BTCUSD"


def test_btc_symbol_owner_is_btc_hypothesis() -> None:
    assert resolve_symbol_owner("BTCUSD") == "btc-spot-tsmom-4h"


def test_spy_symbol_owner_from_paper_guard_overlay() -> None:
    assert resolve_symbol_owner("SPY") == "spy-equity-tsmom-1d"


def test_account_halt_blocks_before_slice(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    monkeypatch.setattr("week_trader.paper_account_guards.repo_root", lambda: tmp_path)
    guards = json.loads((repo / "paper_account_guards.json").read_text(encoding="utf-8"))
    (tmp_path / "paper_account_guards.json").write_text(json.dumps(guards), encoding="utf-8")
    halt = tmp_path / "paper" / "_shared" / "ACCOUNT_HALT"
    halt.parent.mkdir(parents=True, exist_ok=True)
    halt.write_text("stop\n", encoding="utf-8")
    with pytest.raises(PaperAccountGuardError, match="account HALT"):
        assert_account_halt_absent()


def test_enforce_guards_rejects_wrong_owner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    monkeypatch.setattr("week_trader.paper_account_guards.repo_root", lambda: tmp_path)
    (tmp_path / "paper_account_guards.json").write_text(
        (repo / "paper_account_guards.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    intent = {"symbol": "BTCUSD", "side": "buy", "qty": "0.001", "reference_price_usd": 90000}
    with pytest.raises(PaperAccountGuardError, match="owned by"):
        enforce_shared_account_guards(
            "other-hypothesis",
            intent,
            "test-intent",
            fetch_positions=lambda: [],
            fetch_open_orders=lambda: [],
        )


def test_opposite_open_order_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    monkeypatch.setattr("week_trader.paper_account_guards.repo_root", lambda: tmp_path)
    (tmp_path / "paper_account_guards.json").write_text(
        (repo / "paper_account_guards.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    intent = {"symbol": "BTCUSD", "side": "buy", "qty": "0.001", "reference_price_usd": 90000}
    open_orders = [{"symbol": "BTCUSD", "side": "sell", "status": "new", "qty": "0.001"}]
    with pytest.raises(PaperAccountGuardError, match="opposite open order"):
        enforce_shared_account_guards(
            "btc-spot-tsmom-4h",
            intent,
            "test-intent",
            fetch_positions=lambda: [],
            fetch_open_orders=lambda: open_orders,
        )


def test_capital_slice_exceeded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    monkeypatch.setattr("week_trader.paper_account_guards.repo_root", lambda: tmp_path)
    (tmp_path / "paper_account_guards.json").write_text(
        (repo / "paper_account_guards.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    intent = {"symbol": "BTCUSD", "side": "buy", "qty": "1", "reference_price_usd": 90000}
    positions = [{"symbol": "BTCUSD", "qty": "0.05", "market_value": "4500"}]
    with pytest.raises(PaperAccountGuardError, match="capital slice exceeded"):
        enforce_shared_account_guards(
            "btc-spot-tsmom-4h",
            intent,
            "test-intent",
            fetch_positions=lambda: positions,
            fetch_open_orders=lambda: [],
        )


def test_build_client_order_id_uses_fill_tag() -> None:
    cid = build_client_order_id("btc-spot-tsmom-4h", "market-long-btcusd", "wt-btc-spot-tsmom-4h")
    assert cid.startswith("wt-btc-spot-tsmom-4h--")
    assert len(cid) <= 48


def test_build_alpaca_order_body_includes_client_order_id() -> None:
    body = build_alpaca_order_body(
        {
            "symbol": "BTCUSD",
            "side": "buy",
            "qty": "0.001",
            "client_order_id": "wt-btc-spot-tsmom-4h--market-long-btcusd",
        }
    )
    assert body["client_order_id"] == "wt-btc-spot-tsmom-4h--market-long-btcusd"


def test_paper_order_blocks_on_account_halt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATE_LOG_HMAC_SECRET", "test-hmac-secret-for-ci-only")
    from week_trader.gate_log import write_gate_log
    from week_trader.util import repo_root, sha256_json

    halt = repo_root() / "paper" / "_shared" / "ACCOUNT_HALT"
    halt.parent.mkdir(parents=True, exist_ok=True)
    halt.write_text("stop\n", encoding="utf-8")

    freeze = json.loads(
        (repo_root() / "hypotheses" / "btc-spot-tsmom-4h" / "freeze_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    log = write_gate_log(
        "btc-spot-tsmom-4h",
        "trade",
        freeze_manifest_hash=sha256_json(freeze),
        state_hash="s",
        request_hash="r",
        response_body_hash="b",
        model_id="jev-1.14.0",
        passed=True,
        threshold_compare={"pass": True},
        response_body={"answers": {}},
    )

    with pytest.raises(PaperOrderError, match="account HALT"):
        paper_order(
            "market-long-btcusd",
            log,
            fetch_positions=lambda: [],
            fetch_open_orders=lambda: [],
        )

    halt.unlink(missing_ok=True)
