from __future__ import annotations

from week_trader.paper_account_guards import load_guards_config
from week_trader.paper_forward import evaluate_eem_xlf_csmom_1d_signal


def _closes_map(base: float, drift: float, n: int = 25) -> dict[str, list[float]]:
    eem = [base + drift * i for i in range(n)]
    xlf = [base - drift * i for i in range(n)]
    return {"EEM": eem, "XLF": xlf}


def test_eem_xlf_csmom_picks_relative_winner() -> None:
    closes = _closes_map(100.0, 0.5)
    signal = evaluate_eem_xlf_csmom_1d_signal(closes, hypothesis_id="eem-xlf-csmom-1d")
    assert signal["side"] == "long"
    assert signal["target_symbol"] == "EEM"
    assert signal["formation_returns"]["EEM"] > signal["formation_returns"]["XLF"]


def test_eem_xlf_guard_slice() -> None:
    cfg = load_guards_config()
    slices = cfg.get("strategy_slices")
    assert isinstance(slices, dict)
    row = slices.get("eem-xlf-csmom-1d")
    assert isinstance(row, dict)
    assert row.get("max_notional_usd") == 5000
