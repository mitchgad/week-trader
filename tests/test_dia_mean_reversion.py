from __future__ import annotations

from week_trader.paper_account_guards import load_guards_config
from week_trader.paper_forward import evaluate_dia_mean_reversion_1d_signal


def test_dia_mean_reversion_long_on_negative_week() -> None:
    closes = [100.0, 99.0, 98.0, 97.0, 96.0, 95.0]
    signal = evaluate_dia_mean_reversion_1d_signal(closes, hypothesis_id="dia-mean-reversion-1d")
    assert signal["side"] == "long"
    assert signal["formation_return"] < 0


def test_dia_mean_reversion_flat_on_positive_week() -> None:
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
    signal = evaluate_dia_mean_reversion_1d_signal(closes, hypothesis_id="dia-mean-reversion-1d")
    assert signal["side"] == "flat"
    assert signal["formation_return"] > 0


def test_paper_guard_overlay_loads_dia_slice() -> None:
    cfg = load_guards_config()
    slices = cfg.get("strategy_slices")
    assert isinstance(slices, dict)
    dia = slices.get("dia-mean-reversion-1d")
    assert isinstance(dia, dict)
    assert dia.get("max_notional_usd") == 5000
    owners = cfg.get("symbol_owners")
    assert isinstance(owners, dict)
    assert owners.get("DIA") == "dia-mean-reversion-1d"
