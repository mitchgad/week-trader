from __future__ import annotations

import math

import pytest

from week_trader.paper_account_guards import load_guards_config, resolve_symbol_owner
from week_trader.paper_forward import evaluate_iwm_vol_overlay_signal


def test_paper_guard_overlay_registers_iwm_owner() -> None:
    config = load_guards_config()
    assert resolve_symbol_owner("IWM", config) == "iwm-vol-overlay-1d"
    slice_entry = config["strategy_slices"]["iwm-vol-overlay-1d"]
    assert slice_entry["max_notional_usd"] == 5000


def test_iwm_vol_overlay_signal_long_when_momentum_and_low_vol() -> None:
    closes = [100.0] * 280
    for i in range(1, len(closes)):
        closes[i] = closes[i - 1] * 1.001
    signal = evaluate_iwm_vol_overlay_signal(closes, hypothesis_id="iwm-vol-overlay-1d")
    assert signal["base_long"] is True
    assert signal["side"] == "long"
    assert signal["target_weight"] > 0.0


def test_iwm_vol_overlay_signal_flat_when_momentum_negative() -> None:
    closes = [100.0] * 280
    for i in range(1, len(closes)):
        closes[i] = closes[i - 1] * 0.999
    signal = evaluate_iwm_vol_overlay_signal(closes, hypothesis_id="iwm-vol-overlay-1d")
    assert signal["base_long"] is False
    assert signal["side"] == "flat"
    assert signal["target_weight"] == 0.0


def test_build_jev_state_includes_iwm_spec_fields() -> None:
    from week_trader.jev_state import build_jev_state

    state = build_jev_state("iwm-vol-overlay-1d", gate="spec")
    fields = state["fields"]
    assert fields["manifest_single_equity_symbol_matches"] is True
    assert fields["vol_overlay_long_only_capped"] is True
    assert fields["spec_long_only_leverage_excerpt_present"] is True
    assert fields["overlay_unproven_statement_present"] is True
    assert fields["overlay_portability_acknowledged"] is True
    assert fields["primary_citations_present"] is True
    assert fields["disconfirmers_documented"] is True
    assert fields["venue_contract_equity_alpaca"] is True
    assert fields["promotion_proof_alpaca_equity_forward_only"] is True
