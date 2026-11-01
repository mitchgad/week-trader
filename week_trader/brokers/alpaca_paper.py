from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlparse

import requests

PAPER_ALPACA_NETLOC = "paper-api.alpaca.markets"
DATA_ALPACA_NETLOC = "data.alpaca.markets"
DEFAULT_PAPER_BASE_URL = f"https://{PAPER_ALPACA_NETLOC}"
DEFAULT_DATA_BASE_URL = f"https://{DATA_ALPACA_NETLOC}"
CRYPTO_4H_TIMEFRAME = "4Hour"
EQUITY_1D_TIMEFRAME = "1Day"


class AlpacaPaperError(Exception):
    pass


HttpGet = Callable[..., requests.Response]
HttpPost = Callable[..., requests.Response]


def _auth_headers() -> dict[str, str]:
    key, secret = load_alpaca_paper_credentials()
    return {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
        "Content-Type": "application/json",
    }


def alpaca_paper_request(
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    http_get: HttpGet | None = None,
    http_post: HttpPost | None = None,
    timeout: int = 30,
    base_url: str | None = None,
) -> Any:
    """Authenticated request to Alpaca paper API only."""
    base = base_url or paper_base_url()
    url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
    headers = _auth_headers()
    try:
        if method.upper() == "GET":
            get = http_get or requests.get
            response = get(url, headers=headers, params=params, timeout=timeout)
        elif method.upper() == "POST":
            post = http_post or requests.post
            response = post(url, headers=headers, json=json_body, params=params, timeout=timeout)
        else:
            raise AlpacaPaperError(f"unsupported HTTP method {method!r}")
    except requests.Timeout as exc:
        raise AlpacaPaperError("Alpaca paper timeout — fail closed") from exc
    except requests.RequestException as exc:
        raise AlpacaPaperError(f"Alpaca paper request error — fail closed: {exc}") from exc

    if response.status_code >= 400:
        raise AlpacaPaperError(f"Alpaca paper HTTP {response.status_code} — fail closed")

    body_bytes = getattr(response, "content", None)
    if not body_bytes:
        return {}
    try:
        payload = response.json()
    except ValueError as exc:
        raise AlpacaPaperError("Alpaca paper malformed JSON — fail closed") from exc
    return payload


def fetch_paper_account(**kwargs: Any) -> dict[str, Any]:
    payload = alpaca_paper_request("GET", "/v2/account", **kwargs)
    if not isinstance(payload, dict):
        raise AlpacaPaperError("Alpaca account response must be object — fail closed")
    return payload


def fetch_paper_positions(**kwargs: Any) -> list[dict[str, Any]]:
    payload = alpaca_paper_request("GET", "/v2/positions", **kwargs)
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    if isinstance(payload, dict):
        positions = payload.get("positions")
        if isinstance(positions, list):
            return [p for p in positions if isinstance(p, dict)]
    return []


def fetch_paper_open_orders(**kwargs: Any) -> list[dict[str, Any]]:
    payload = alpaca_paper_request(
        "GET",
        "/v2/orders",
        params={"status": "open", "limit": "500"},
        **kwargs,
    )
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def fetch_paper_open_orders(**kwargs: Any) -> list[dict[str, Any]]:
    """Open orders on the Alpaca paper account (paper-api only)."""
    payload = alpaca_paper_request(
        "GET",
        "/v2/orders",
        params={"status": "open"},
        **kwargs,
    )
    if isinstance(payload, list):
        return [order for order in payload if isinstance(order, dict)]
    return []


def fetch_paper_order(order_id: str, **kwargs: Any) -> dict[str, Any]:
    payload = alpaca_paper_request("GET", f"/v2/orders/{order_id}", **kwargs)
    if not isinstance(payload, dict):
        raise AlpacaPaperError("Alpaca order response must be object — fail closed")
    return payload


def require_paper_alpaca_host(url: str) -> str:
    """Hard-refuse any host other than Alpaca paper (v1: no live endpoints)."""
    raw = url.strip()
    if not raw:
        raise AlpacaPaperError("ALPACA_PAPER_BASE_URL empty — fail closed")
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    netloc = parsed.netloc.lower()
    if not netloc:
        raise AlpacaPaperError("invalid ALPACA_PAPER_BASE_URL — fail closed")
    if netloc != PAPER_ALPACA_NETLOC:
        raise AlpacaPaperError(f"refusing non-paper Alpaca host {netloc!r} — v1 paper only")
    return DEFAULT_PAPER_BASE_URL


def load_alpaca_paper_credentials() -> tuple[str, str]:
    key = os.environ.get("ALPACA_PAPER_KEY")
    secret = os.environ.get("ALPACA_PAPER_SECRET")
    if not key or not secret:
        raise AlpacaPaperError("ALPACA_PAPER_KEY/SECRET missing — fail closed")
    return key, secret


def paper_base_url() -> str:
    raw = os.environ.get("ALPACA_PAPER_BASE_URL", DEFAULT_PAPER_BASE_URL)
    return require_paper_alpaca_host(raw)


def require_alpaca_data_host(url: str) -> str:
    """Read-only market data host (v1: no order endpoints on this host)."""
    raw = url.strip()
    if not raw:
        raise AlpacaPaperError("ALPACA_DATA_BASE_URL empty — fail closed")
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    netloc = parsed.netloc.lower()
    if not netloc:
        raise AlpacaPaperError("invalid ALPACA_DATA_BASE_URL — fail closed")
    if netloc != DATA_ALPACA_NETLOC:
        raise AlpacaPaperError(f"refusing non-data Alpaca host {netloc!r} — v1 data only")
    return DEFAULT_DATA_BASE_URL


def data_base_url() -> str:
    raw = os.environ.get("ALPACA_DATA_BASE_URL", DEFAULT_DATA_BASE_URL)
    return require_alpaca_data_host(raw)


def fetch_crypto_4h_bar_closes(
    symbol: str,
    *,
    min_bars: int = 8,
    lookback_days: int = 14,
    http_get: HttpGet | None = None,
) -> list[float]:
    """
    Completed 4h crypto bar closes from Alpaca market data (observation only).
    Uses the same paper credentials as the trading API.
    """
    if min_bars < 2:
        raise AlpacaPaperError("min_bars must be at least 2")
    start = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "symbols": symbol,
        "timeframe": CRYPTO_4H_TIMEFRAME,
        "start": start,
        "limit": "10000",
        "sort": "asc",
    }
    payload = alpaca_paper_request(
        "GET",
        "/v1beta3/crypto/us/bars",
        params=params,
        http_get=http_get,
        base_url=data_base_url(),
    )
    if not isinstance(payload, dict):
        raise AlpacaPaperError("Alpaca bars response must be object — fail closed")
    bars_root = payload.get("bars")
    if not isinstance(bars_root, dict):
        raise AlpacaPaperError("Alpaca bars missing bars object — fail closed")
    series = bars_root.get(symbol)
    if not isinstance(series, list):
        raise AlpacaPaperError(f"Alpaca bars missing series for {symbol!r} — fail closed")
    closes: list[float] = []
    for bar in series:
        if not isinstance(bar, dict):
            continue
        close = bar.get("c")
        if close is None:
            continue
        try:
            closes.append(float(close))
        except (TypeError, ValueError) as exc:
            raise AlpacaPaperError("Alpaca bar close not numeric — fail closed") from exc
    if len(closes) < min_bars:
        raise AlpacaPaperError(
            f"need at least {min_bars} 4h closes for signal; got {len(closes)} — fail closed"
        )
    return closes


def fetch_equity_daily_closes_volumes(
    symbol: str,
    *,
    min_bars: int = 25,
    lookback_days: int = 400,
    http_get: HttpGet | None = None,
) -> tuple[list[float], list[float]]:
    """Daily equity closes and share volumes (Campbell et al. volume–return tests)."""
    if min_bars < 2:
        raise AlpacaPaperError("min_bars must be at least 2")
    normalized = symbol.strip().upper()
    start = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "symbols": normalized,
        "timeframe": EQUITY_1D_TIMEFRAME,
        "start": start,
        "limit": "10000",
        "sort": "asc",
        "adjustment": "split",
    }
    payload = alpaca_paper_request(
        "GET",
        "/v2/stocks/bars",
        params=params,
        http_get=http_get,
        base_url=data_base_url(),
    )
    if not isinstance(payload, dict):
        raise AlpacaPaperError("Alpaca equity bars response must be object — fail closed")
    bars_root = payload.get("bars")
    if not isinstance(bars_root, dict):
        raise AlpacaPaperError("Alpaca equity bars missing bars object — fail closed")
    series = bars_root.get(normalized)
    if not isinstance(series, list):
        raise AlpacaPaperError(f"Alpaca equity bars missing series for {normalized!r} — fail closed")
    closes: list[float] = []
    volumes: list[float] = []
    for bar in series:
        if not isinstance(bar, dict):
            continue
        close = bar.get("c")
        vol = bar.get("v")
        if close is None or vol is None:
            continue
        try:
            closes.append(float(close))
            volumes.append(float(vol))
        except (TypeError, ValueError) as exc:
            raise AlpacaPaperError("Alpaca bar fields not numeric — fail closed") from exc
    if len(closes) < min_bars:
        raise AlpacaPaperError(
            f"need at least {min_bars} daily bars for signal; got {len(closes)} — fail closed"
        )
    return closes, volumes


def fetch_equity_cash_dividends(
    symbols: list[str],
    *,
    start_date: str,
    end_date: str,
    http_get: HttpGet | None = None,
) -> list[dict[str, Any]]:
    """Cash dividend corporate actions from Alpaca market data (read-only)."""
    normalized = [s.strip().upper() for s in symbols if isinstance(s, str) and s.strip()]
    if not normalized:
        return []
    params = {
        "cas_symbols": ",".join(normalized),
        "cas_types": "cash_dividend",
        "cas_start": start_date,
        "cas_end": end_date,
        "cas_data_quality": "complete",
    }
    payload = alpaca_paper_request(
        "GET",
        "/v1/corporate-actions",
        params={k: str(v) for k, v in params.items()},
        http_get=http_get,
        base_url=data_base_url(),
    )
    if not isinstance(payload, dict):
        raise AlpacaPaperError("Alpaca corporate actions response must be object — fail closed")
    corporate = payload.get("corporate_actions")
    if not isinstance(corporate, dict):
        return []
    rows = corporate.get("cash_dividends")
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            out.append(row)
    return out


def fetch_equity_daily_bar_closes(
    symbol: str,
    *,
    min_bars: int = 130,
    lookback_days: int = 400,
    http_get: HttpGet | None = None,
) -> list[float]:
    """Completed 1Day US equity bar closes from Alpaca market data."""
    if min_bars < 2:
        raise AlpacaPaperError("min_bars must be at least 2")
    normalized = symbol.strip().upper()
    start = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "symbols": normalized,
        "timeframe": EQUITY_1D_TIMEFRAME,
        "start": start,
        "limit": "10000",
        "sort": "asc",
        "adjustment": "split",
    }
    payload = alpaca_paper_request(
        "GET",
        "/v2/stocks/bars",
        params=params,
        http_get=http_get,
        base_url=data_base_url(),
    )
    if not isinstance(payload, dict):
        raise AlpacaPaperError("Alpaca equity bars response must be object — fail closed")
    bars_root = payload.get("bars")
    if not isinstance(bars_root, dict):
        raise AlpacaPaperError("Alpaca equity bars missing bars object — fail closed")
    series = bars_root.get(normalized)
    if not isinstance(series, list):
        series = bars_root.get(symbol)
    if not isinstance(series, list):
        raise AlpacaPaperError(f"Alpaca equity bars missing series for {normalized!r} — fail closed")
    closes: list[float] = []
    for bar in series:
        if not isinstance(bar, dict):
            continue
        close = bar.get("c")
        if close is None:
            continue
        try:
            closes.append(float(close))
        except (TypeError, ValueError) as exc:
            raise AlpacaPaperError("Alpaca equity bar close not numeric — fail closed") from exc
    if len(closes) < min_bars:
        raise AlpacaPaperError(
            f"need at least {min_bars} daily closes for signal; got {len(closes)} — fail closed"
        )
    return closes


def build_alpaca_order_body(intent: dict[str, Any]) -> dict[str, str]:
    for field in ("symbol", "side", "qty"):
        if field not in intent:
            raise AlpacaPaperError(f"order intent missing {field!r}")
    side = str(intent["side"]).lower()
    if side not in {"buy", "sell"}:
        raise AlpacaPaperError(f"invalid side {side!r}")
    body = {
        "symbol": str(intent["symbol"]),
        "qty": str(intent["qty"]),
        "side": side,
        "type": str(intent.get("type", "market")),
        "time_in_force": str(intent.get("time_in_force", "gtc")),
    }
    client_order_id = intent.get("client_order_id")
    if isinstance(client_order_id, str) and client_order_id.strip():
        body["client_order_id"] = client_order_id.strip()[:48]
    return body


def submit_alpaca_paper_order(
    *,
    intent: dict[str, Any],
    http_post: HttpPost | None = None,
) -> dict[str, Any]:
    """POST a paper order to Alpaca. Only paper-api host; credentials required."""
    body = build_alpaca_order_body(intent)
    return alpaca_paper_request("POST", "/v2/orders", json_body=body, http_post=http_post)
