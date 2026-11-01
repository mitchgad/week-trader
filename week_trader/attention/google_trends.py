from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

# pytrends still passes method_whitelist= to urllib3 Retry (removed in urllib3 v2).
import urllib3.util.retry as _urllib3_retry

_orig_retry_init = _urllib3_retry.Retry.__init__


def _retry_init_compat(self, *args: Any, **kwargs: Any) -> None:
    if "method_whitelist" in kwargs:
        kwargs["allowed_methods"] = kwargs.pop("method_whitelist")
    _orig_retry_init(self, *args, **kwargs)


_urllib3_retry.Retry.__init__ = _retry_init_compat  # type: ignore[method-assign]

TRENDS_EXPLORE_URL = "https://trends.google.com/trends/api/explore"
TRENDS_MULTILINE_URL = "https://trends.google.com/trends/api/widgetdata/multiline"

# Google Trends serves daily points only when each request window is <= ~270 days.
PYTRENDS_DAILY_CHUNK_DAYS = 269
DEFAULT_MAX_STALE_DAYS = 4


class GoogleTrendsError(Exception):
    pass


@dataclass(frozen=True)
class TrendsDailyRow:
    date_utc: str
    negative_keyword: int
    baseline_keyword: int
    is_partial: bool

    @property
    def ratio(self) -> float:
        baseline = max(self.baseline_keyword, 1)
        return float(self.negative_keyword) / float(baseline)


def fetch_daily_interest_pair(
    negative_keyword: str,
    baseline_keyword: str,
    *,
    timeframe: str = "today 5-y",
    geo: str = "US",
    lookback_rows: int = 252,
    max_stale_days: int = DEFAULT_MAX_STALE_DAYS,
    session: requests.Session | None = None,
) -> list[TrendsDailyRow]:
    """
    Pull relative search interest for two keywords from Google Trends (free, no API key).
    Uses chunked daily windows when lookback requires more than a few months of history.
    Raises GoogleTrendsError when the series cannot be retrieved or fails freshness checks.
    """
    errors: list[str] = []
    if lookback_rows >= 60:
        try:
            rows = _fetch_daily_interest_pytrends_chunked(
                negative_keyword,
                baseline_keyword,
                lookback_rows=lookback_rows,
                geo=geo,
            )
            validate_trends_daily_series(
                rows,
                lookback_rows=lookback_rows,
                max_stale_days=max_stale_days,
            )
            return rows
        except GoogleTrendsError as exc:
            errors.append(f"chunked daily: {exc}")

    try:
        rows = _fetch_daily_interest_pytrends(
            negative_keyword,
            baseline_keyword,
            timeframe=timeframe,
            geo=geo,
        )
        validate_trends_daily_series(
            rows,
            lookback_rows=lookback_rows,
            max_stale_days=max_stale_days,
        )
        return rows
    except GoogleTrendsError as exc:
        errors.append(str(exc))
    try:
        rows = _fetch_daily_interest_direct(
            negative_keyword,
            baseline_keyword,
            timeframe=timeframe,
            geo=geo,
            session=session,
        )
        validate_trends_daily_series(
            rows,
            lookback_rows=lookback_rows,
            max_stale_days=max_stale_days,
        )
        return rows
    except GoogleTrendsError as exc:
        errors.append(str(exc))
    raise GoogleTrendsError("; ".join(errors))


def validate_trends_daily_series(
    rows: list[TrendsDailyRow],
    *,
    lookback_rows: int,
    max_stale_days: int = DEFAULT_MAX_STALE_DAYS,
    reference_date: date | None = None,
) -> None:
    """Fail closed when Trends data is empty, weekly-coarse, all-zero, or stale."""
    completed = [row for row in rows if not row.is_partial]
    if len(completed) < lookback_rows + 1:
        raise GoogleTrendsError(
            f"need at least {lookback_rows + 1} completed trend days; got {len(completed)}"
        )

    recent = completed[-min(14, len(completed)) :]
    gaps = _day_gaps(parse_trends_row_date(r.date_utc) for r in recent)
    if gaps and sum(gaps) / len(gaps) > 2.5:
        raise GoogleTrendsError("trends series appears weekly-coarse, not daily")

    ref = reference_date or datetime.now(timezone.utc).date()
    last = completed[-1]
    last_day = parse_trends_row_date(last.date_utc)
    stale_days = (ref - last_day).days
    if stale_days > max_stale_days:
        raise GoogleTrendsError(
            f"trends last completed day {last_day.isoformat()} is {stale_days}d stale (max {max_stale_days}d)"
        )

    window = completed[-(lookback_rows + 1) :]
    if all(row.negative_keyword == 0 and row.baseline_keyword == 0 for row in window):
        raise GoogleTrendsError("trends lookback window is all-zero (missing or rate-limited)")


def parse_trends_row_date(date_utc: str) -> date:
    cleaned = date_utc.strip()
    if len(cleaned) >= 10 and cleaned[4] == "-" and cleaned[7] == "-":
        return date.fromisoformat(cleaned[:10])
    raise GoogleTrendsError(f"trends date not ISO daily: {date_utc!r}")


def _day_gaps(days: Any) -> list[int]:
    ordered = sorted(days)
    out: list[int] = []
    for i in range(1, len(ordered)):
        delta = (ordered[i] - ordered[i - 1]).days
        if delta > 0:
            out.append(delta)
    return out


def _fetch_daily_interest_pytrends_chunked(
    negative_keyword: str,
    baseline_keyword: str,
    *,
    lookback_rows: int,
    geo: str,
) -> list[TrendsDailyRow]:
    try:
        from pytrends.request import TrendReq
    except ImportError as exc:
        raise GoogleTrendsError("pytrends not installed for Trends fetch") from exc

    end = datetime.now(timezone.utc).date()
    # Calendar span with buffer for weekends and partial current day.
    span_days = lookback_rows + 60
    start = end - timedelta(days=span_days)
    client = TrendReq(hl="en-US", tz=360, retries=3, backoff_factor=1.0)

    merged: dict[str, TrendsDailyRow] = {}
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=PYTRENDS_DAILY_CHUNK_DAYS), end)
        timeframe = f"{cursor.isoformat()} {chunk_end.isoformat()}"
        try:
            client.build_payload([negative_keyword, baseline_keyword], timeframe=timeframe, geo=geo)
            frame = client.interest_over_time()
        except Exception as exc:
            raise GoogleTrendsError(f"pytrends chunk {timeframe} failed: {exc}") from exc
        if frame is None or frame.empty:
            raise GoogleTrendsError(f"pytrends chunk {timeframe} returned empty frame")
        for idx, row in frame.iterrows():
            partial = bool(row.get("isPartial", False))
            try:
                negative_val = int(row[negative_keyword])
                baseline_val = int(row[baseline_keyword])
            except (TypeError, ValueError, KeyError) as exc:
                raise GoogleTrendsError("pytrends value not numeric") from exc
            day = str(idx.date())
            merged[day] = TrendsDailyRow(
                date_utc=day,
                negative_keyword=negative_val,
                baseline_keyword=baseline_val,
                is_partial=partial,
            )
        cursor = chunk_end + timedelta(days=1)
        time.sleep(0.4)

    if len(merged) < lookback_rows + 5:
        raise GoogleTrendsError(f"pytrends chunked merge too short: {len(merged)} rows")
    ordered_days = sorted(merged.keys())
    return [merged[d] for d in ordered_days]


def _fetch_daily_interest_direct(
    negative_keyword: str,
    baseline_keyword: str,
    *,
    timeframe: str,
    geo: str,
    session: requests.Session | None,
) -> list[TrendsDailyRow]:
    client = session or requests.Session()
    client.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (compatible; week-trader/0.1; +https://github.com/mitchgad/week-trader)"
            ),
        }
    )
    comparison = [
        {"keyword": negative_keyword, "geo": geo, "time": timeframe},
        {"keyword": baseline_keyword, "geo": geo, "time": timeframe},
    ]
    req_payload = {"comparisonItem": comparison, "category": 0, "property": ""}
    explore = _trends_get_json(client, TRENDS_EXPLORE_URL, {"hl": "en-US", "tz": "360", "req": json.dumps(req_payload)})
    widgets = explore.get("widgets")
    if not isinstance(widgets, list):
        raise GoogleTrendsError("Trends explore missing widgets")
    timeline_widget: dict[str, Any] | None = None
    for widget in widgets:
        if isinstance(widget, dict) and widget.get("id") == "TIMESERIES":
            timeline_widget = widget
            break
    if timeline_widget is None:
        raise GoogleTrendsError("Trends TIMESERIES widget missing")

    token = timeline_widget.get("token")
    req = timeline_widget.get("request")
    if not isinstance(token, str) or not isinstance(req, dict):
        raise GoogleTrendsError("Trends widget token/request missing")

    time.sleep(0.35)
    series_payload = _trends_get_json(
        client,
        TRENDS_MULTILINE_URL,
        {"hl": "en-US", "tz": "360", "req": json.dumps(req), "token": token},
    )
    timeline = series_payload.get("default", {}).get("timelineData")
    if not isinstance(timeline, list) or not timeline:
        raise GoogleTrendsError("Trends timeline empty")

    rows: list[TrendsDailyRow] = []
    for point in timeline:
        if not isinstance(point, dict):
            continue
        values = point.get("value")
        if not isinstance(values, list) or len(values) < 2:
            continue
        try:
            negative_val = int(values[0])
            baseline_val = int(values[1])
        except (TypeError, ValueError) as exc:
            raise GoogleTrendsError("Trends value not numeric") from exc
        formatted = point.get("formattedTime")
        if not isinstance(formatted, str) or not formatted.strip():
            continue
        rows.append(
            TrendsDailyRow(
                date_utc=formatted.strip(),
                negative_keyword=negative_val,
                baseline_keyword=baseline_val,
                is_partial=bool(point.get("isPartial")),
            )
        )
    if len(rows) < 30:
        raise GoogleTrendsError(f"Trends series too short: {len(rows)} rows")
    return rows


def _fetch_daily_interest_pytrends(
    negative_keyword: str,
    baseline_keyword: str,
    *,
    timeframe: str,
    geo: str,
) -> list[TrendsDailyRow]:
    try:
        from pytrends.request import TrendReq
    except ImportError as exc:
        raise GoogleTrendsError("pytrends not installed for Trends fallback") from exc
    client = TrendReq(hl="en-US", tz=360, retries=3, backoff_factor=1.0)
    client.build_payload([negative_keyword, baseline_keyword], timeframe=timeframe, geo=geo)
    frame = client.interest_over_time()
    if frame is None or frame.empty:
        raise GoogleTrendsError("pytrends returned empty frame")
    rows: list[TrendsDailyRow] = []
    for idx, row in frame.iterrows():
        partial = bool(row.get("isPartial", False))
        try:
            negative_val = int(row[negative_keyword])
            baseline_val = int(row[baseline_keyword])
        except (TypeError, ValueError, KeyError) as exc:
            raise GoogleTrendsError("pytrends value not numeric") from exc
        rows.append(
            TrendsDailyRow(
                date_utc=str(idx.date()),
                negative_keyword=negative_val,
                baseline_keyword=baseline_val,
                is_partial=partial,
            )
        )
    if len(rows) < 30:
        raise GoogleTrendsError(f"pytrends series too short: {len(rows)} rows")
    return rows


def _trends_get_json(session: requests.Session, url: str, params: dict[str, str]) -> dict[str, Any]:
    last_error: GoogleTrendsError | None = None
    for attempt in range(5):
        try:
            response = session.get(url, params=params, timeout=30)
        except requests.RequestException as exc:
            last_error = GoogleTrendsError(f"Trends HTTP error: {exc}")
            time.sleep(1.5 * (attempt + 1))
            continue
        if response.status_code == 429:
            last_error = GoogleTrendsError("Trends HTTP 429")
            time.sleep(2.0 * (attempt + 1))
            continue
        if response.status_code >= 400:
            raise GoogleTrendsError(f"Trends HTTP {response.status_code}")
        text = response.text
        if text.startswith(")]}',"):
            text = text[5:]
        if text.lstrip().startswith("<"):
            last_error = GoogleTrendsError(f"Trends non-JSON response (HTTP {response.status_code})")
            time.sleep(2.0 * (attempt + 1))
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GoogleTrendsError("Trends malformed JSON") from exc
        if not isinstance(payload, dict):
            raise GoogleTrendsError("Trends payload must be object")
        return payload
    if last_error is not None:
        raise last_error
    raise GoogleTrendsError("Trends request failed")
