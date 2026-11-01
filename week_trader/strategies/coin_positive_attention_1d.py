from __future__ import annotations

from typing import Sequence

from week_trader.attention.google_trends import TrendsDailyRow
from week_trader.strategies.gld_negative_attention_1d import (
    NegativeAttentionSignalError,
    _quantile,
)


def evaluate_positive_attention_1d(
    rows: Sequence[TrendsDailyRow],
    *,
    hypothesis_id: str,
    symbol: str,
    lookback_rows: int = 252,
    high_ratio_quantile: float = 0.8,
    positive_keyword: str,
    baseline_keyword: str,
) -> dict[str, object]:
    """Long when positive/baseline Trends ratio is in top historical quantile; else flat."""
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
    side = "long" if today_ratio >= threshold else "flat"
    return {
        "strategy": hypothesis_id,
        "signal_family": "positive_attention_ratio",
        "symbol": symbol.upper(),
        "side": side,
        "attention_date": today.date_utc,
        "positive_keyword": positive_keyword,
        "baseline_keyword": baseline_keyword,
        "ratio": today_ratio,
        "high_ratio_threshold": threshold,
        "lookback_rows": lookback_rows,
        "high_ratio_quantile": high_ratio_quantile,
        "completed_trend_days": len(completed),
    }
