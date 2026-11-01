from __future__ import annotations

import math


class TermCarrySignalError(Exception):
    pass


def evaluate_vgit_shy_term_carry_1d(
    closes_by_symbol: dict[str, list[float]],
    *,
    hypothesis_id: str,
    lookback: int = 63,
    entry_z: float = 1.0,
) -> dict[str, object]:
    """
    Bond term-structure carry proxy: long VGIT / short SHY when log(VGIT/SHY) is
    rich vs its rolling mean (steep curve / carry to intermediate duration).
    """
    vgit = closes_by_symbol.get("VGIT")
    shy = closes_by_symbol.get("SHY")
    if vgit is None or shy is None:
        raise TermCarrySignalError("VGIT and SHY closes required")
    if len(vgit) < lookback + 1 or len(shy) < lookback + 1:
        raise TermCarrySignalError(f"need {lookback + 1} daily closes for term carry")
    spreads: list[float] = []
    for i in range(-lookback, 0):
        if vgit[i] <= 0 or shy[i] <= 0:
            raise TermCarrySignalError("non-positive close in carry window")
        spreads.append(math.log(vgit[i] / shy[i]))
    current = spreads[-1]
    mean = sum(spreads) / len(spreads)
    var = sum((s - mean) ** 2 for s in spreads) / max(len(spreads) - 1, 1)
    std = math.sqrt(var) if var > 0 else 0.0
    spread_z = (current - mean) / std if std > 0 else 0.0
    if spread_z >= entry_z:
        return {
            "strategy": hypothesis_id,
            "side": "pairs",
            "long_symbol": "VGIT",
            "short_symbol": "SHY",
            "spread_z": spread_z,
            "lookback_days": lookback,
            "signal_family": "term_structure_carry",
        }
    return {
        "strategy": hypothesis_id,
        "side": "flat",
        "spread_z": spread_z,
        "lookback_days": lookback,
        "signal_family": "term_structure_carry",
    }
