from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from week_trader.brokers.alpaca_paper import AlpacaPaperError, fetch_equity_cash_dividends
from week_trader.manifest import load_data_manifest, resolve_manifest_for_hypothesis
from week_trader.prereg import load_preregistration
from week_trader.util import load_json

FetchDividends = Callable[..., list[dict[str, Any]]]


def manifest_cost_bps(hypothesis_id: str) -> tuple[float, float]:
    prereg = load_preregistration(hypothesis_id)
    manifest_path = resolve_manifest_for_hypothesis(hypothesis_id, prereg)
    manifest = load_data_manifest(manifest_path)
    costs = manifest.get("costs")
    if not isinstance(costs, dict):
        return 0.0, 0.0
    fee = _float_or_zero(costs.get("fee_bps_per_side"))
    slip = _float_or_zero(costs.get("slippage_bps_per_side"))
    return fee, slip


def manifest_instrument_class(hypothesis_id: str) -> str | None:
    prereg = load_preregistration(hypothesis_id)
    manifest_path = resolve_manifest_for_hypothesis(hypothesis_id, prereg)
    manifest = load_data_manifest(manifest_path)
    instrument = manifest.get("instrument_class")
    return str(instrument) if isinstance(instrument, str) else None


def build_forward_pnl_adjustments(
    hypothesis_id: str,
    *,
    raw_snapshot: dict[str, Any],
    positions: list[dict[str, Any]],
    forward_directory: Path,
    fetch_dividends: FetchDividends | None = None,
    synced_utc: str | None = None,
) -> dict[str, Any]:
    """
    Raw Alpaca paper figures vs adjusted (dividends Alpaca omits, minus manifest fee/slippage on fills).
    Forward paper only — not used for backtests or Jev scoring.
    """
    fee_bps, slippage_bps = manifest_cost_bps(hypothesis_id)
    events_path = forward_directory / "events.jsonl"
    fills = load_fill_events(events_path)
    estimated_costs = estimate_fill_costs_usd(fills, fee_bps=fee_bps, slippage_bps=slippage_bps)

    dividend_usd = 0.0
    dividend_detail: dict[str, Any] = {"credits": [], "fetch_error": None}
    instrument = manifest_instrument_class(hypothesis_id)
    if instrument in {"equity", "equity_etf"}:
        dividend_usd, dividend_detail = accrue_equity_dividends(
            hypothesis_id,
            forward_directory=forward_directory,
            positions=positions,
            fills=fills,
            fetch_dividends=fetch_dividends or fetch_equity_cash_dividends,
            synced_utc=synced_utc,
        )

    raw_equity = _float_or_none(raw_snapshot.get("equity"))
    raw_last = _float_or_none(raw_snapshot.get("last_equity"))
    adjustment_net = dividend_usd - estimated_costs
    adjusted_equity = _apply_adjustment(raw_equity, adjustment_net)
    adjusted_last = _apply_adjustment(raw_last, adjustment_net)

    raw_block = {
        "equity": raw_equity,
        "last_equity": raw_last,
        "cash": _float_or_none(raw_snapshot.get("cash")),
        "buying_power": _float_or_none(raw_snapshot.get("buying_power")),
        "unrealized_pl": _float_or_none(raw_snapshot.get("unrealized_pl")),
    }
    adjusted_block = {
        "equity": adjusted_equity,
        "last_equity": adjusted_last,
        "cash": raw_block["cash"],
        "buying_power": raw_block["buying_power"],
        "unrealized_pl": raw_block["unrealized_pl"],
    }

    return {
        "raw": raw_block,
        "adjusted": adjusted_block,
        "adjustments": {
            "cumulative_dividends_usd": round(dividend_usd, 6),
            "cumulative_estimated_costs_usd": round(estimated_costs, 6),
            "net_adjustment_usd": round(adjustment_net, 6),
            "fee_bps_per_side": fee_bps,
            "slippage_bps_per_side": slippage_bps,
            "cost_method": "manifest_bps_per_fill_notional_one_side",
            "dividend_method": "alpaca_cash_dividends_times_shares_before_ex_date",
            "dividend_detail": dividend_detail,
        },
    }


def load_fill_events(events_path: Path) -> list[dict[str, Any]]:
    if not events_path.is_file():
        return []
    fills: list[dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event_type") != "fill":
            continue
        payload = event.get("payload")
        if isinstance(payload, dict):
            fills.append(payload)
    return fills


def estimate_fill_costs_usd(
    fills: list[dict[str, Any]],
    *,
    fee_bps: float,
    slippage_bps: float,
) -> float:
    bps_per_side = fee_bps + slippage_bps
    total = 0.0
    for fill in fills:
        status = str(fill.get("status", "")).lower()
        if status not in {"filled", "partially_filled"}:
            continue
        qty = _float_or_zero(fill.get("filled_qty"))
        price = _float_or_zero(fill.get("filled_avg_price"))
        if qty <= 0 or price <= 0:
            continue
        notional = qty * price
        total += notional * bps_per_side / 10_000.0
    return total


def accrue_equity_dividends(
    hypothesis_id: str,
    *,
    forward_directory: Path,
    positions: list[dict[str, Any]],
    fills: list[dict[str, Any]],
    fetch_dividends: FetchDividends,
    synced_utc: str | None,
) -> tuple[float, dict[str, Any]]:
    ledger_path = forward_directory / "dividend_ledger.json"
    ledger = _load_dividend_ledger(ledger_path)
    credited_ids = {str(item.get("ca_id")) for item in ledger.get("credits", []) if item.get("ca_id")}

    symbols = _dividend_symbols(positions, hypothesis_id)
    if not symbols:
        return _ledger_total_usd(ledger), {"credits": ledger.get("credits", []), "fetch_error": None}

    start_date, end_date = _dividend_window(forward_directory)
    detail: dict[str, Any] = {"credits": list(ledger.get("credits", [])), "fetch_error": None}
    try:
        dividends = fetch_dividends(symbols, start_date=start_date, end_date=end_date)
    except AlpacaPaperError as exc:
        detail["fetch_error"] = str(exc)
        return _ledger_total_usd(ledger), detail

    now = synced_utc or _utc_now()
    for row in dividends:
        ca_id = str(row.get("id", ""))
        if not ca_id or ca_id in credited_ids:
            continue
        symbol = str(row.get("symbol", "")).strip().upper()
        ex_date = _parse_date(row.get("ex_date"))
        rate = _float_or_zero(row.get("rate"))
        if ex_date is None or rate <= 0 or not symbol:
            continue
        if ex_date > date.today():
            continue
        shares = shares_before_ex_date(fills, symbol, ex_date)
        if shares <= 0:
            continue
        usd = shares * rate
        credit = {
            "ca_id": ca_id,
            "symbol": symbol,
            "ex_date": ex_date.isoformat(),
            "shares": shares,
            "rate": rate,
            "usd": round(usd, 6),
            "credited_at_utc": now,
        }
        ledger.setdefault("credits", []).append(credit)
        credited_ids.add(ca_id)
        detail["credits"].append(credit)

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return _ledger_total_usd(ledger), detail


def shares_before_ex_date(fills: list[dict[str, Any]], symbol: str, ex_date: date) -> float:
    target = symbol.strip().upper()
    qty = 0.0
    for fill in _sorted_fills(fills):
        fill_symbol = str(fill.get("symbol", "")).strip().upper()
        if fill_symbol != target:
            continue
        fill_day = _fill_date(fill)
        if fill_day is None or fill_day >= ex_date:
            continue
        delta = _signed_fill_qty(fill)
        qty += delta
    return max(qty, 0.0)


def _dividend_symbols(positions: list[dict[str, Any]], hypothesis_id: str) -> list[str]:
    from week_trader.paper_forward import manifest_universe_symbols

    manifest_syms = set(manifest_universe_symbols(hypothesis_id))
    out: set[str] = set()
    for position in positions:
        sym = position.get("symbol")
        qty = _float_or_zero(position.get("qty"))
        if not isinstance(sym, str) or qty == 0:
            continue
        normalized = sym.strip().upper()
        if normalized in manifest_syms:
            out.add(normalized)
    return sorted(out)


def _dividend_window(forward_directory: Path) -> tuple[str, str]:
    events_path = forward_directory / "events.jsonl"
    start = date.today().replace(year=date.today().year - 2)
    if events_path.is_file():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = event.get("timestamp_utc")
            if isinstance(ts, str):
                parsed = _parse_datetime(ts)
                if parsed is not None:
                    start = min(start, parsed.date())
                    break
    end = date.today().isoformat()
    return start.isoformat(), end


def _load_dividend_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"credits": []}
    loaded = load_json(path)
    if not isinstance(loaded, dict):
        return {"credits": []}
    credits = loaded.get("credits")
    if not isinstance(credits, list):
        return {"credits": []}
    return {"credits": [c for c in credits if isinstance(c, dict)]}


def _ledger_total_usd(ledger: dict[str, Any]) -> float:
    total = 0.0
    for item in ledger.get("credits", []):
        if isinstance(item, dict):
            total += _float_or_zero(item.get("usd"))
    return total


def _sorted_fills(fills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(fill: dict[str, Any]) -> tuple[str, str]:
        ts = fill.get("filled_at") or fill.get("synced_at_utc") or ""
        return (str(ts), str(fill.get("order_id", "")))

    return sorted(fills, key=sort_key)


def _signed_fill_qty(fill: dict[str, Any]) -> float:
    qty = _float_or_zero(fill.get("filled_qty"))
    side = str(fill.get("side", "")).lower()
    if side == "sell":
        return -qty
    return qty


def _fill_date(fill: dict[str, Any]) -> date | None:
    for key in ("filled_at", "synced_at_utc"):
        raw = fill.get(key)
        if isinstance(raw, str):
            parsed = _parse_datetime(raw)
            if parsed is not None:
                return parsed.date()
    return None


def _apply_adjustment(value: float | None, delta: float) -> float | None:
    if value is None:
        return None
    return value + delta


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_datetime(value: str) -> datetime | None:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_or_zero(value: Any) -> float:
    parsed = _float_or_none(value)
    return parsed if parsed is not None else 0.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
