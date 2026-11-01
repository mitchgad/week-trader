from __future__ import annotations

import json
from pathlib import Path

import pytest

from week_trader.paper_forward import (
    PaperForwardError,
    append_forward_event,
    build_paper_account_book,
    evaluate_tsmom_4h_signal,
    forward_dir,
    register_pending_order,
    run_forward_monitor_tick,
)
from week_trader.util import repo_root


def test_evaluate_tsmom_4h_long_when_formation_positive() -> None:
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]
    signal = evaluate_tsmom_4h_signal(closes)
    assert signal["side"] == "long"
    assert signal["formation_log_return"] > 0


def test_evaluate_tsmom_4h_flat_when_formation_non_positive() -> None:
    closes = [107.0, 106.0, 105.0, 104.0, 103.0, 102.0, 101.0, 100.0]
    signal = evaluate_tsmom_4h_signal(closes)
    assert signal["side"] == "flat"


def test_forward_monitor_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("week_trader.paper_forward.repo_root", lambda: tmp_path)
    result = run_forward_monitor_tick("_template", dry_run=True)
    assert result["dry_run"] is True
    status_path = tmp_path / "paper" / "_template" / "forward" / "status.json"
    assert status_path.is_file()


def test_forward_monitor_syncs_fills(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("week_trader.paper_forward.repo_root", lambda: tmp_path)
    hypothesis_id = "_template"
    register_pending_order(hypothesis_id, "ord-1", {"order_intent_id": "i1"})
    register_pending_order(hypothesis_id, "ord-2", {"order_intent_id": "i2"})

    def fake_account() -> dict[str, object]:
        return {
            "equity": "10000",
            "cash": "5000",
            "last_equity": "9900",
            "buying_power": "5000",
        }

    def fake_positions() -> list[dict[str, object]]:
        return [{"symbol": "BTCUSD", "unrealized_pl": "12.5"}]

    def fake_open_orders() -> list[dict[str, object]]:
        return []

    def fake_order(order_id: str) -> dict[str, object]:
        if order_id == "ord-1":
            return {
                "id": order_id,
                "status": "filled",
                "symbol": "BTCUSD",
                "filled_qty": "0.01",
                "filled_avg_price": "42000",
            }
        return {"id": order_id, "status": "canceled"}

    result = run_forward_monitor_tick(
        hypothesis_id,
        fetch_account=fake_account,
        fetch_positions=fake_positions,
        fetch_open_orders=fake_open_orders,
        fetch_order=fake_order,
    )
    assert result["fills_synced_this_tick"] == 2
    events_path = forward_dir(hypothesis_id)
    assert (events_path / "events.jsonl").is_file()
    lines = (events_path / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    types = {json.loads(line)["event_type"] for line in lines}
    assert "pnl_snapshot" in types
    assert "fill" in types
    pending = json.loads((events_path / "pending_orders.json").read_text(encoding="utf-8"))
    assert pending == {}


def test_build_paper_account_book_summarizes_positions_and_orders() -> None:
    book = build_paper_account_book(
        {"equity": "100000", "cash": "50000", "buying_power": "75000", "last_equity": "100000"},
        [{"symbol": "BTCUSD", "qty": "0.01", "market_value": "400", "side": "long"}],
        [{"id": "ord-1", "symbol": "BTCUSD", "side": "buy", "qty": "0.001", "status": "new"}],
        synced_utc="2026-11-01T00:00:00Z",
    )
    assert book["source"] == "alpaca_paper"
    assert book["open_order_count"] == 1
    assert book["position_count"] == 1
    assert book["buying_power"] == 75000.0


def test_forward_monitor_halt_blocks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("week_trader.paper_forward.repo_root", lambda: tmp_path)
    halt = tmp_path / "paper" / "_template" / "HALT"
    halt.parent.mkdir(parents=True, exist_ok=True)
    halt.write_text("stop\n", encoding="utf-8")
    with pytest.raises(PaperForwardError, match="HALT"):
        run_forward_monitor_tick("_template")


def test_paper_order_registers_forward_tracking(
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
    ):
        if target.endswith("hypothesis_dir"):
            monkeypatch.setattr(
                target,
                lambda hypothesis_id, root=tmp_path: root / "hypotheses" / hypothesis_id,
            )
        else:
            monkeypatch.setattr(target, _root)
    monkeypatch.setenv("GATE_LOG_HMAC_SECRET", "test-hmac-secret-for-ci-only")
    monkeypatch.setenv("ALPACA_PAPER_KEY", "k")
    monkeypatch.setenv("ALPACA_PAPER_SECRET", "s")

    repo = Path(__file__).resolve().parents[1]
    for name in ("HYPOTHESIS.md", "preregistration.json", "freeze_manifest.json"):
        src = repo / "hypotheses" / "_template" / name
        dest = tmp_path / "hypotheses" / "_template" / name
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
    intents = tmp_path / "paper" / "_template" / "intents"
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
        json.loads((tmp_path / "hypotheses" / "_template" / "freeze_manifest.json").read_text())
    )
    log = write_gate_log(
        "_template",
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

    class FakeResponse:
        status_code = 200
        content = b'{"id":"ord-forward-1","status":"accepted","symbol":"XLCIUSD"}'

        @staticmethod
        def json() -> dict[str, str]:
            return {"id": "ord-forward-1", "status": "accepted", "symbol": "XLCIUSD"}

    def fake_post(*_args: object, **_kwargs: object) -> FakeResponse:
        return FakeResponse()

    import week_trader.brokers.alpaca_paper as alpaca_paper_module

    monkeypatch.setattr(alpaca_paper_module.requests, "post", fake_post)

    from week_trader.paper_order import paper_order

    paper_order(
        "fwd-intent",
        log,
        dry_run=False,
        fetch_positions=lambda: [],
        fetch_open_orders=lambda: [],
    )
    pending = json.loads(
        (tmp_path / "paper" / "_template" / "forward" / "pending_orders.json").read_text()
    )
    assert "ord-forward-1" in pending
