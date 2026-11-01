from __future__ import annotations

from typing import Sequence

from week_trader.attention.google_trends import TrendsDailyRow


class NegativeAttentionSignalError(Exception):
    pass


def evaluate_gld_negative_attention_1d(
    rows: Sequence[TrendsDailyRow],
    *,
    hypothesis_id: str,
    symbol: str = "GLD",
    lookback_rows: int = 252,
    high_ratio_quantile: float = 0.8,
    negative_keyword: str = "gold crash",
    baseline_keyword: str = "gold price",
) -> dict[str, object]:
    """
    C2-style negative attention: flat when crash/baseline search ratio is in the
    top historical quintile; otherwise long. Uses only completed (non-partial) days.
    """
    if not 0.0 < high_ratio_quantile < 1.0:
        raise NegativeAttentionSignalError("high_ratio_quantile must be between 0 and 1")
    completed = [row for row in rows if not row.is_partial]
    if len(completed) < lookback_rows + 1:
        raise NegativeAttentionSignalError(
            f"need at least {lookback_rows + 1} completed trend days; got {len(completed)}"
        )
    window = completed[-(lookback_rows + 1) :]
    history = window[:-1]
    today = window[-1]
    ratios = [row.ratio for row in history]
    threshold = _quantile(ratios, high_ratio_quantile)
    today_ratio = today.ratio
    side = "flat" if today_ratio >= threshold else "long"
    return {
        "strategy": hypothesis_id,
        "signal_family": "negative_attention_ratio",
        "symbol": symbol.upper(),
        "side": side,
        "attention_date": today.date_utc,
        "negative_keyword": negative_keyword,
        "baseline_keyword": baseline_keyword,
        "ratio": today_ratio,
        "high_ratio_threshold": threshold,
        "lookback_rows": lookback_rows,
        "high_ratio_quantile": high_ratio_quantile,
        "completed_trend_days": len(completed),
    }


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise NegativeAttentionSignalError("empty ratio history")
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]
