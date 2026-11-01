from __future__ import annotations

import json
from pathlib import Path

import pytest

from week_trader.jev_state import build_jev_state
from week_trader.paper_forward import (
    append_forward_event,
    read_last_signal_side,
    run_forward_monitor_tick,
    summarize_spot_position,
)


def test_build_jev_state_includes_spec_fields_for_btc() -> None:
    state = build_jev_state("btc-spot-tsmom-4h", gate="spec")
    fields = state["fields"]
    assert fields["venue_contract_spot_only"] is True
    assert fields["disconfirmers_documented"] is True
    assert fields["manifest_cost_block_present"] is True
    assert fields["engine_parity_required"] is True
    assert fields["proof_contract_present"] is True
    assert fields["forbidden_perp_funding_proof_in_prereg"] is True
    assert fields["promotion_proof_alpaca_spot_forward_only"] is True


def test_build_jev_state_uses_forward_monitor_for_trade_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("week_trader.jev_state.repo_root", lambda: tmp_path)
    monkeypatch.setattr("week_trader.paper_forward.repo_root", lambda: tmp_path)
    hypothesis_id = "btc-spot-tsmom-4h"
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "hypotheses/btc-spot-tsmom-4h/preregistration.json",
        "hypotheses/btc-spot-tsmom-4h/freeze_manifest.json",
        "hypotheses/btc-spot-tsmom-4h/HYPOTHESIS.md",
        "data/manifests/btc-spot-tsmom-4h-alpaca.yaml",
        "risk_limits.json",
    ):
        src = repo / rel
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8"))

    def fake_account() -> dict[str, object]:
        return {"equity": "100000", "cash": "50000", "last_equity": "100000"}

    def fake_positions() -> list[dict[str, object]]:
        return []

    run_forward_monitor_tick(
        hypothesis_id,
        fetch_account=fake_account,
        fetch_positions=fake_positions,
        fetch_order=lambda _oid: {"status": "canceled"},
    )
    append_forward_event(
        hypothesis_id,
        "signal",
        {"side": "flat", "strategy": "btc-spot-tsmom-4h"},
    )

    state = build_jev_state(hypothesis_id, gate="trade")
    fields = state["fields"]
    assert fields["forward_monitor_present"] is True
    assert fields["data_fresh"] is True
    assert fields["within_risk_bands"] is True
    assert fields["last_signal_side"] == "flat"
    assert fields["btc_spot_open"] is False


def test_summarize_spot_position_matches_manifest_symbol() -> None:
    positions = [{"symbol": "BTCUSD", "qty": "0.01", "market_value": "400"}]
    summary = summarize_spot_position(positions, "BTC/USD")
    assert summary["open"] is True
    assert summary["qty"] == 0.01


def test_read_last_signal_side_from_events(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    events.write_text(
        json.dumps(
            {
                "event_type": "signal",
                "payload": {"side": "long"},
            }
        )
        + "\n"
        + json.dumps(
            {
                "event_type": "signal",
                "payload": {"side": "flat"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert read_last_signal_side(events) == "flat"
