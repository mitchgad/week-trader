from __future__ import annotations


class MaxShortSignalError(Exception):
    pass


def evaluate_xbi_max_short_1d(
    closes: list[float],
    *,
    hypothesis_id: str,
    max_lookback_days: int = 21,
    history_days: int = 252,
    high_max_quantile: float = 0.8,
) -> dict[str, object]:
    """
    Bali, Cakici & Whitelaw MAX lottery: short when max daily return over
    max_lookback_days is in the top historical quantile; else flat.
    """
    if len(closes) < history_days + max_lookback_days + 1:
        raise MaxShortSignalError("insufficient history for MAX short signal")
    daily_returns: list[float] = []
    for i in range(1, len(closes)):
        if closes[i - 1] <= 0:
            raise MaxShortSignalError("non-positive close")
        daily_returns.append(closes[i] / closes[i - 1] - 1.0)
    max_values: list[float] = []
    for end in range(max_lookback_days, len(daily_returns) + 1):
        window = daily_returns[end - max_lookback_days : end]
        max_values.append(max(window))
    today_max = max_values[-1]
    history = max_values[-(history_days + 1) : -1]
    ordered = sorted(history)
    idx = min(len(ordered) - 1, max(0, int(round(high_max_quantile * (len(ordered) - 1)))))
    threshold = ordered[idx]
    side = "short" if today_max >= threshold else "flat"
    return {
        "strategy": hypothesis_id,
        "symbol": "XBI",
        "side": side,
        "signal_family": "max_lottery_short",
        "today_max_daily_return": today_max,
        "high_max_threshold": threshold,
        "max_lookback_days": max_lookback_days,
        "last_close": closes[-1],
    }
