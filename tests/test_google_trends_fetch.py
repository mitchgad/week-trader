from __future__ import annotations

from datetime import date, timedelta

import pytest

from week_trader.attention.google_trends import (
    GoogleTrendsError,
    TrendsDailyRow,
    validate_trends_daily_series,
)


def _daily_rows(count: int, *, end: date, partial_last: bool = False) -> list[TrendsDailyRow]:
    rows: list[TrendsDailyRow] = []
    for i in range(count):
        day = end - timedelta(days=count - i)
        rows.append(
            TrendsDailyRow(
                date_utc=day.isoformat(),
                negative_keyword=5 + (i % 7),
                baseline_keyword=40,
                is_partial=False,
            )
        )
    if partial_last:
        rows.append(
            TrendsDailyRow(
                date_utc=(end + timedelta(days=1)).isoformat(),
                negative_keyword=1,
                baseline_keyword=40,
                is_partial=True,
            )
        )
    return rows


def test_validate_rejects_stale_last_completed_day() -> None:
    ref = date(2026, 11, 1)
    rows = _daily_rows(260, end=date(2026, 10, 25))
    with pytest.raises(GoogleTrendsError, match="stale"):
        validate_trends_daily_series(rows, lookback_rows=252, max_stale_days=4, reference_date=ref)


def test_validate_rejects_weekly_coarse_series() -> None:
    ref = date(2026, 11, 1)
    rows = [
        TrendsDailyRow(
            date_utc=(ref - timedelta(days=7 * (259 - i))).isoformat(),
            negative_keyword=10,
            baseline_keyword=50,
            is_partial=False,
        )
        for i in range(260)
    ]
    with pytest.raises(GoogleTrendsError, match="weekly-coarse"):
        validate_trends_daily_series(rows, lookback_rows=252, max_stale_days=4, reference_date=ref)


def test_validate_accepts_fresh_daily_series() -> None:
    ref = date(2026, 11, 1)
    rows = _daily_rows(260, end=date(2026, 10, 31))
    validate_trends_daily_series(rows, lookback_rows=252, max_stale_days=4, reference_date=ref)


def test_validate_rejects_all_zero_window() -> None:
    ref = date(2026, 11, 1)
    rows = [
        TrendsDailyRow(
            date_utc=(ref - timedelta(days=259 - i)).isoformat(),
            negative_keyword=0,
            baseline_keyword=0,
            is_partial=False,
        )
        for i in range(260)
    ]
    with pytest.raises(GoogleTrendsError, match="all-zero"):
        validate_trends_daily_series(rows, lookback_rows=252, max_stale_days=4, reference_date=ref)
