from __future__ import annotations


class SizeSpreadSignalError(Exception):
    pass


def evaluate_vb_vv_size_spread_1d(
    closes_by_symbol: dict[str, list[float]],
    *,
    hypothesis_id: str,
    formation_days: int = 21,
) -> dict[str, object]:
    """
    Fama-French size spread: long VB (small) and short VV (large) when small-cap
    trailing return exceeds large-cap over the formation window; else flat.
    """
    vb = closes_by_symbol.get("VB")
    vv = closes_by_symbol.get("VV")
    if vb is None or vv is None:
        raise SizeSpreadSignalError("VB and VV closes required")
    if len(vb) < formation_days + 1 or len(vv) < formation_days + 1:
        raise SizeSpreadSignalError(f"need {formation_days + 1} closes for size spread")
    vb_ret = vb[-1] / vb[-(formation_days + 1)] - 1.0
    vv_ret = vv[-1] / vv[-(formation_days + 1)] - 1.0
    spread = vb_ret - vv_ret
    if spread > 0:
        return {
            "strategy": hypothesis_id,
            "side": "pairs",
            "long_symbol": "VB",
            "short_symbol": "VV",
            "formation_days": formation_days,
            "vb_return": vb_ret,
            "vv_return": vv_ret,
            "size_spread_return": spread,
            "signal_family": "smb_spread",
        }
    return {
        "strategy": hypothesis_id,
        "side": "flat",
        "formation_days": formation_days,
        "vb_return": vb_ret,
        "vv_return": vv_ret,
        "size_spread_return": spread,
        "signal_family": "smb_spread",
    }
