from __future__ import annotations

import os
from typing import Any, Callable
from urllib.parse import urlparse

import requests

PAPER_ALPACA_NETLOC = "paper-api.alpaca.markets"
DEFAULT_PAPER_BASE_URL = f"https://{PAPER_ALPACA_NETLOC}"


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
) -> Any:
    """Authenticated request to Alpaca paper API only."""
    base = paper_base_url()
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


def build_alpaca_order_body(intent: dict[str, Any]) -> dict[str, str]:
    for field in ("symbol", "side", "qty"):
        if field not in intent:
            raise AlpacaPaperError(f"order intent missing {field!r}")
    side = str(intent["side"]).lower()
    if side not in {"buy", "sell"}:
        raise AlpacaPaperError(f"invalid side {side!r}")
    return {
        "symbol": str(intent["symbol"]),
        "qty": str(intent["qty"]),
        "side": side,
        "type": str(intent.get("type", "market")),
        "time_in_force": str(intent.get("time_in_force", "gtc")),
    }


def submit_alpaca_paper_order(
    *,
    intent: dict[str, Any],
    http_post: HttpPost | None = None,
) -> dict[str, Any]:
    """POST a paper order to Alpaca. Only paper-api host; credentials required."""
    body = build_alpaca_order_body(intent)
    return alpaca_paper_request("POST", "/v2/orders", json_body=body, http_post=http_post)
