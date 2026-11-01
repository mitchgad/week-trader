from __future__ import annotations

import json
from pathlib import Path

import pytest

from week_trader.paper_forward import record_signal
from week_trader.paper_forward_order import (
    PaperForwardOrderError,
    assert_alpaca_paper_host_pinned,
    submit_paper_order_for_signal,
)
from week_trader.signal_intent import signal_is_flat, signal_matches_order_intent


def test_signal_is_flat() -> None:
    assert signal_is_flat({"side": "flat"})
    assert not signal_is_flat({"side": "long"})


def test_signal_matches_pairs_long_leg() -> None:
    signal = {"side": "pairs", "long_symbol": "IEF", "short_symbol": "TLT"}
    intent = {"symbol": "IEF", "side": "buy", "qty": "50"}
    assert signal_matches_order_intent(signal, intent)


def test_signal_matches_pairs_short_leg() -> None:
    signal = {"side": "pairs", "long_symbol": "VB", "short_symbol": "VV"}
    intent = {"symbol": "VV", "side": "sell", "qty": "18"}
    assert signal_matches_order_intent(signal, intent)


def test_signal_matches_buy_intent() -> None:
    signal = {"side": "long", "last_close": 100.0}
    intent = {"symbol": "BTCUSD", "side": "buy", "qty": "0.001"}
    assert signal_matches_order_intent(signal, intent)


def test_flat_signal_does_not_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    gate_called = False

    def fake_gate(_hid: str, _gate: str) -> Path:
        nonlocal gate_called
        gate_called = True
        raise AssertionError("gate must not run for flat signal")

    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets")
    result = submit_paper_order_for_signal(
        "btc-spot-tsmom-4h",
        {"side": "flat"},
        run_jev_gate_fn=fake_gate,
    )
    assert result["submitted"] is False
    assert result["reason"] == "flat_signal_no_order"
    assert gate_called is False


def test_fail_closed_on_live_alpaca_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", "https://api.alpaca.markets")
    with pytest.raises(PaperForwardOrderError, match="refusing non-paper"):
        assert_alpaca_paper_host_pinned()


def test_paper_url_pin_allows_paper_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets")
    assert assert_alpaca_paper_host_pinned() == "https://paper-api.alpaca.markets"


def test_gate_runs_before_paper_order(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def _root() -> Path:
        return tmp_path

    for target in (
        "week_trader.util.repo_root",
        "week_trader.gate_log.repo_root",
        "week_trader.manifest.repo_root",
        "week_trader.paper_order.repo_root",
        "week_trader.paper_forward.repo_root",
        "week_trader.paper_account_guards.repo_root",
        "week_trader.paper_forward_order.repo_root",
    ):
        monkeypatch.setattr(target, _root)

    monkeypatch.setenv("GATE_LOG_HMAC_SECRET", "test-hmac-secret-for-ci-only")
    monkeypatch.setenv("ALPACA_PAPER_KEY", "k")
    monkeypatch.setenv("ALPACA_PAPER_SECRET", "s")
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets")

    repo = Path(__file__).resolve().parents[1]
    hid = "_template"
    for name in ("HYPOTHESIS.md", "preregistration.json", "freeze_manifest.json"):
        src = repo / "hypotheses" / hid / name
        dest = tmp_path / "hypotheses" / hid / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8"))
    (tmp_path / "data" / "manifests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "manifests" / "example-btc-spot.yaml").write_text(
        (repo / "data" / "manifests" / "example-btc-spot.yaml").read_text(encoding="utf-8")
    )
    (tmp_path / "risk_limits.json").write_text(
        (repo / "risk_limits.json").read_text(encoding="utf-8")
    )
    (tmp_path / "paper_account_guards.json").write_text(
        (repo / "paper_account_guards.json").read_text(encoding="utf-8")
    )
    intents = tmp_path / "paper" / hid / "intents"
    intents.mkdir(parents=True, exist_ok=True)
    intents.joinpath("fwd-intent.json").write_text(
        json.dumps(
            {
                "symbol": "XLCIUSD",
                "side": "buy",
                "qty": "0.001",
                "reference_price_usd": 100.0,
            }
        )
        + "\n"
    )

    from week_trader.gate_log import write_gate_log
    from week_trader.util import sha256_json

    freeze_hash = sha256_json(
        json.loads((tmp_path / "hypotheses" / hid / "freeze_manifest.json").read_text())
    )

    def fake_gate(_hid: str, gate: str) -> Path:
        calls.append(f"gate:{gate}")
        return write_gate_log(
            hid,
            "trade",
            freeze_manifest_hash=freeze_hash,
            state_hash="s",
            request_hash="r",
            response_body_hash="b",
            model_id="jev-1.14.0",
            passed=True,
            threshold_compare={"pass": True},
            response_body={"answers": {}},
        )

    def fake_paper_order(*_args: object, **_kwargs: object) -> dict[str, object]:
        calls.append("paper_order")
        return {"status": "validated_dry_run", "dry_run": True, "broker_calls": 0}

    signal = {"side": "long", "last_close": 100.0}
    result = submit_paper_order_for_signal(
        hid,
        signal,
        dry_run=True,
        run_jev_gate_fn=fake_gate,
        paper_order_fn=fake_paper_order,
        fetch_positions=lambda: [],
        fetch_open_orders=lambda: [],
    )
    assert calls == ["gate:trade", "paper_order"]
    assert result.get("validated_dry_run") is True


def test_account_halt_blocks_before_broker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _root() -> Path:
        return tmp_path

    for target in (
        "week_trader.util.repo_root",
        "week_trader.gate_log.repo_root",
        "week_trader.manifest.repo_root",
        "week_trader.paper_order.repo_root",
        "week_trader.paper_forward.repo_root",
        "week_trader.paper_account_guards.repo_root",
        "week_trader.paper_forward_order.repo_root",
    ):
        monkeypatch.setattr(target, _root)

    monkeypatch.setenv("GATE_LOG_HMAC_SECRET", "test-hmac-secret-for-ci-only")
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets")

    repo = Path(__file__).resolve().parents[1]
    hid = "_template"
    for name in ("HYPOTHESIS.md", "preregistration.json", "freeze_manifest.json"):
        src = repo / "hypotheses" / hid / name
        dest = tmp_path / "hypotheses" / hid / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8"))
    (tmp_path / "risk_limits.json").write_text(
        (repo / "risk_limits.json").read_text(encoding="utf-8")
    )
    (tmp_path / "paper_account_guards.json").write_text(
        (repo / "paper_account_guards.json").read_text(encoding="utf-8")
    )
    (tmp_path / "data" / "manifests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "manifests" / "example-btc-spot.yaml").write_text(
        (repo / "data" / "manifests" / "example-btc-spot.yaml").read_text(encoding="utf-8")
    )
    halt = tmp_path / "paper" / "_shared" / "ACCOUNT_HALT"
    halt.parent.mkdir(parents=True, exist_ok=True)
    halt.write_text("halt\n", encoding="utf-8")
    intents = tmp_path / "paper" / hid / "intents"
    intents.mkdir(parents=True, exist_ok=True)
    intents.joinpath("fwd-intent.json").write_text(
        json.dumps({"symbol": "XLCIUSD", "side": "buy", "qty": "0.001", "reference_price_usd": 100.0})
        + "\n"
    )

    from week_trader.gate_log import write_gate_log
    from week_trader.util import sha256_json

    freeze_hash = sha256_json(
        json.loads((tmp_path / "hypotheses" / hid / "freeze_manifest.json").read_text())
    )

    def fake_gate(_hid: str, _gate: str) -> Path:
        return write_gate_log(
            hid,
            "trade",
            freeze_manifest_hash=freeze_hash,
            state_hash="s",
            request_hash="r",
            response_body_hash="b",
            model_id="jev-1.14.0",
            passed=True,
            threshold_compare={"pass": True},
            response_body={"answers": {}},
        )

    result = submit_paper_order_for_signal(
        hid,
        {"side": "long"},
        dry_run=False,
        run_jev_gate_fn=fake_gate,
        fetch_positions=lambda: [],
        fetch_open_orders=lambda: [],
    )
    assert result["submitted"] is False
    assert result["reason"] == "paper_order_rejected"
    assert "HALT" in result["detail"].upper()


def test_client_order_id_tag_prefix_on_dry_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _root() -> Path:
        return tmp_path

    for target in (
        "week_trader.util.repo_root",
        "week_trader.gate_log.repo_root",
        "week_trader.manifest.repo_root",
        "week_trader.paper_order.repo_root",
        "week_trader.paper_forward.repo_root",
        "week_trader.paper_account_guards.repo_root",
        "week_trader.paper_forward_order.repo_root",
    ):
        monkeypatch.setattr(target, _root)

    monkeypatch.setenv("GATE_LOG_HMAC_SECRET", "test-hmac-secret-for-ci-only")
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets")

    repo = Path(__file__).resolve().parents[1]
    hid = "_template"
    for name in ("HYPOTHESIS.md", "preregistration.json", "freeze_manifest.json"):
        src = repo / "hypotheses" / hid / name
        dest = tmp_path / "hypotheses" / hid / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8"))
    (tmp_path / "data" / "manifests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "manifests" / "example-btc-spot.yaml").write_text(
        (repo / "data" / "manifests" / "example-btc-spot.yaml").read_text(encoding="utf-8")
    )
    (tmp_path / "risk_limits.json").write_text(
        (repo / "risk_limits.json").read_text(encoding="utf-8")
    )
    (tmp_path / "paper_account_guards.json").write_text(
        (repo / "paper_account_guards.json").read_text(encoding="utf-8")
    )
    intents = tmp_path / "paper" / hid / "intents"
    intents.mkdir(parents=True, exist_ok=True)
    intents.joinpath("fwd-intent.json").write_text(
        json.dumps({"symbol": "XLCIUSD", "side": "buy", "qty": "0.001", "reference_price_usd": 100.0})
        + "\n"
    )

    from week_trader.gate_log import write_gate_log
    from week_trader.util import sha256_json

    freeze_hash = sha256_json(
        json.loads((tmp_path / "hypotheses" / hid / "freeze_manifest.json").read_text())
    )

    def fake_gate(_hid: str, _gate: str) -> Path:
        return write_gate_log(
            hid,
            "trade",
            freeze_manifest_hash=freeze_hash,
            state_hash="s",
            request_hash="r",
            response_body_hash="b",
            model_id="jev-1.14.0",
            passed=True,
            threshold_compare={"pass": True},
            response_body={"answers": {}},
        )

    result = submit_paper_order_for_signal(
        hid,
        {"side": "long"},
        dry_run=True,
        run_jev_gate_fn=fake_gate,
        fetch_positions=lambda: [],
        fetch_open_orders=lambda: [],
    )
    client_order_id = result["paper_order"]["client_order_id"]
    assert str(client_order_id).startswith("wt-_template--")


def test_record_signal_with_submit_wires_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("week_trader.paper_forward.repo_root", lambda: tmp_path)
    submitted: list[dict[str, object]] = []

    def fake_submit(hid: str, signal: dict[str, object], **kwargs: object) -> dict[str, object]:
        submitted.append({"hid": hid, "signal": signal, "kwargs": kwargs})
        return {"submitted": False, "reason": "mock"}

    monkeypatch.setattr(
        "week_trader.paper_forward_order.submit_paper_order_for_signal",
        fake_submit,
    )
    out = record_signal(
        "btc-spot-tsmom-4h",
        {"side": "long"},
        submit_order=True,
        dry_run=True,
    )
    assert out["recorded"] is True
    assert len(submitted) == 1
    assert submitted[0]["hid"] == "btc-spot-tsmom-4h"
