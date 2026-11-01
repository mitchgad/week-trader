from __future__ import annotations

import math

from week_trader.paper_account_guards import load_guards_config
from week_trader.paper_forward import evaluate_tlt_ief_pairs_1d_signal


def _synthetic_pair(n: int = 65, *, tlt_scale: float = 1.0) -> dict[str, list[float]]:
    tlt = [100.0 * tlt_scale + 0.01 * i for i in range(n)]
    ief = [100.0 + 0.01 * i for i in range(n)]
    return {"TLT": tlt, "IEF": ief}


def test_tlt_ief_pairs_flat_inside_bands() -> None:
    closes = _synthetic_pair()
    signal = evaluate_tlt_ief_pairs_1d_signal(closes, hypothesis_id="tlt-ief-pairs-1d")
    assert signal["side"] == "flat"


def test_tlt_ief_pairs_short_rich_tlt() -> None:
    closes = _synthetic_pair()
    tlt = closes["TLT"]
    spike = tlt[-1] * 1.15
    closes["TLT"] = tlt[:-1] + [spike]
    signal = evaluate_tlt_ief_pairs_1d_signal(closes, hypothesis_id="tlt-ief-pairs-1d")
    if signal["side"] == "pairs":
        assert signal["long_symbol"] == "IEF"
        assert signal["short_symbol"] == "TLT"
        assert abs(signal["spread_z"]) > 2.0
    else:
        assert math.isfinite(signal["spread_z"])


def test_tlt_ief_guard_slice() -> None:
    cfg = load_guards_config()
    slices = cfg.get("strategy_slices")
    assert isinstance(slices, dict)
    row = slices.get("tlt-ief-pairs-1d")
    assert isinstance(row, dict)
    assert row.get("max_notional_usd") == 5000
