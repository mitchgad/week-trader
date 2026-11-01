from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import requests

TRENDS_EXPLORE_URL = "https://trends.google.com/trends/api/explore"
TRENDS_MULTILINE_URL = "https://trends.google.com/trends/api/widgetdata/multiline"


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
    session: requests.Session | None = None,
) -> list[TrendsDailyRow]:
    """
    Pull relative search interest for two keywords from Google Trends (free, no API key).
    Raises GoogleTrendsError when the series cannot be retrieved.
    """
    errors: list[str] = []
    try:
        return _fetch_daily_interest_direct(
            negative_keyword,
            baseline_keyword,
            timeframe=timeframe,
            geo=geo,
            session=session,
        )
    except GoogleTrendsError as exc:
        errors.append(str(exc))
    try:
        return _fetch_daily_interest_pytrends(
            negative_keyword,
            baseline_keyword,
            timeframe=timeframe,
            geo=geo,
        )
    except GoogleTrendsError as exc:
        errors.append(str(exc))
    raise GoogleTrendsError("; ".join(errors))


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
