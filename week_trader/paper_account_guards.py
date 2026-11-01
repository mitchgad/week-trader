from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from week_trader.brokers.alpaca_paper import (
    AlpacaPaperError,
    fetch_paper_open_orders,
    fetch_paper_positions,
)
from week_trader.paper_forward import normalize_alpaca_crypto_symbol
from week_trader.paper_guards_config import merged_guard_view
from week_trader.util import load_json, repo_root

FetchPositions = Callable[..., list[dict[str, Any]]]
FetchOpenOrders = Callable[..., list[dict[str, Any]]]


class PaperAccountGuardError(Exception):
    pass


def guards_config_path() -> Path:
    return repo_root() / "paper_account_guards.json"


def load_guards_config() -> dict[str, Any]:
    path = guards_config_path()
    if not path.is_file():
        raise PaperAccountGuardError("paper_account_guards.json missing")
    data = load_json(path)
    if not isinstance(data, dict):
        raise PaperAccountGuardError("paper_account_guards.json must be an object")
    return data


def normalize_guard_symbol(symbol: str) -> str:
    return normalize_alpaca_crypto_symbol(symbol.strip())


def shared_ledger_dir() -> Path:
    return repo_root() / "paper" / "_shared"


def fill_tag_ledger_path() -> Path:
    return shared_ledger_dir() / "fill_tags.jsonl"


def assert_account_halt_absent(config: dict[str, Any] | None = None) -> None:
    cfg = config or load_guards_config()
    rel = cfg.get("account_halt_file")
    if not isinstance(rel, str) or not rel.strip():
        raise PaperAccountGuardError("account_halt_file missing in guards config")
    halt_path = repo_root() / rel
    if halt_path.is_file():
        raise PaperAccountGuardError("account HALT present — zero orders on shared paper account")


def resolve_symbol_owner(normalized_symbol: str, config: dict[str, Any] | None = None) -> str | None:
    cfg = config or load_guards_config()
    owners = cfg.get("symbol_owners")
    if not isinstance(owners, dict):
        return None
    for key, owner in owners.items():
        if not isinstance(key, str) or not isinstance(owner, str):
            continue
        if normalize_guard_symbol(key) == normalized_symbol:
            return owner
    return None


def strategy_slice(config: dict[str, Any], hypothesis_id: str) -> dict[str, Any]:
    slices = config.get("strategy_slices")
    if not isinstance(slices, dict):
        raise PaperAccountGuardError("strategy_slices missing in guards config")
    entry = slices.get(hypothesis_id)
    if not isinstance(entry, dict):
        raise PaperAccountGuardError(f"no capital slice for hypothesis {hypothesis_id!r}")
    max_notional = entry.get("max_notional_usd")
    fill_tag = entry.get("fill_tag")
    if max_notional is None or not isinstance(fill_tag, str) or not fill_tag.strip():
        raise PaperAccountGuardError(f"invalid capital slice for {hypothesis_id!r}")
    return entry


def build_client_order_id(hypothesis_id: str, order_intent_id: str, fill_tag: str) -> str:
    raw = f"{fill_tag}--{order_intent_id}"
    if len(raw) <= 48:
        return raw
    trimmed = f"{fill_tag[:20]}--{order_intent_id}"[:48]
    return trimmed


def client_order_id_prefix(fill_tag: str) -> str:
    return f"{fill_tag}--"


def enforce_shared_account_guards(
    hypothesis_id: str,
    intent: dict[str, Any],
    order_intent_id: str,
    *,
    fetch_positions: FetchPositions | None = None,
    fetch_open_orders: FetchOpenOrders | None = None,
) -> dict[str, Any]:
    """
    Shared Alpaca paper account guards (v1): account halt, symbol owner, capital slice,
    opposite-side open-order lock, fill tag for client_order_id.
    """
    base_config = load_guards_config()
    config = merged_guard_view(hypothesis_id, base_config)
    assert_account_halt_absent(config)

    symbol_raw = intent.get("symbol")
    if not isinstance(symbol_raw, str) or not symbol_raw.strip():
        raise PaperAccountGuardError("order intent symbol required")
    normalized = normalize_guard_symbol(symbol_raw)
    owner = resolve_symbol_owner(normalized, config)
    if owner is None:
        raise PaperAccountGuardError(f"symbol {normalized!r} has no registered owner")
    if owner != hypothesis_id:
        raise PaperAccountGuardError(
            f"symbol {normalized!r} owned by {owner!r}, not {hypothesis_id!r}"
        )

    slice_entry = strategy_slice(config, hypothesis_id)
    fill_tag = str(slice_entry["fill_tag"])
    max_notional = float(slice_entry["max_notional_usd"])
    client_order_id = build_client_order_id(hypothesis_id, order_intent_id, fill_tag)

    intent_side = str(intent.get("side", "")).lower()
    if intent_side not in {"buy", "sell"}:
        raise PaperAccountGuardError(f"invalid intent side {intent_side!r}")

    get_positions = fetch_positions or fetch_paper_positions
    get_open_orders = fetch_open_orders or fetch_paper_open_orders
    try:
        positions = get_positions()
        open_orders = get_open_orders()
    except AlpacaPaperError as exc:
        raise PaperAccountGuardError(str(exc)) from exc

    _assert_no_opposite_open_orders(normalized, intent_side, open_orders)
    projected_notional = _projected_strategy_notional(
        hypothesis_id,
        normalized,
        intent,
        fill_tag,
        positions,
        open_orders,
    )
    if projected_notional > max_notional:
        raise PaperAccountGuardError(
            f"capital slice exceeded: projected {projected_notional:.2f} USD "
            f"> max {max_notional:.2f} USD for {hypothesis_id!r}"
        )

    return {
        "client_order_id": client_order_id,
        "fill_tag": fill_tag,
        "symbol_normalized": normalized,
        "projected_notional_usd": projected_notional,
        "max_notional_usd": max_notional,
    }


def record_fill_tag_submission(
    hypothesis_id: str,
    *,
    client_order_id: str,
    fill_tag: str,
    symbol: str,
    side: str,
    qty: str,
    order_intent_id: str,
) -> None:
    directory = shared_ledger_dir()
    directory.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hypothesis_id": hypothesis_id,
        "order_intent_id": order_intent_id,
        "fill_tag": fill_tag,
        "client_order_id": client_order_id,
        "symbol": symbol,
        "side": side,
        "qty": qty,
    }
    with fill_tag_ledger_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def _assert_no_opposite_open_orders(
    normalized_symbol: str,
    intent_side: str,
    open_orders: list[dict[str, Any]],
) -> None:
    for order in open_orders:
        raw_symbol = order.get("symbol")
        if not isinstance(raw_symbol, str):
            continue
        if normalize_guard_symbol(raw_symbol) != normalized_symbol:
            continue
        order_side = str(order.get("side", "")).lower()
        if order_side not in {"buy", "sell"}:
            continue
        if order_side == intent_side:
            continue
        status = str(order.get("status", "")).lower()
        if status in {"filled", "canceled", "expired", "rejected"}:
            continue
        raise PaperAccountGuardError(
            f"opposite open order on {normalized_symbol!r}: existing {order_side!r} "
            f"blocks new {intent_side!r}"
        )


def _projected_strategy_notional(
    hypothesis_id: str,
    normalized_symbol: str,
    intent: dict[str, Any],
    fill_tag: str,
    positions: list[dict[str, Any]],
    open_orders: list[dict[str, Any]],
) -> float:
    price = _reference_price_usd(hypothesis_id, intent)
    qty = _float(intent.get("qty"))
    if qty is None or qty <= 0:
        raise PaperAccountGuardError("order intent qty required for capital slice")

    position_notional = 0.0
    for position in positions:
        raw_symbol = position.get("symbol")
        if not isinstance(raw_symbol, str):
            continue
        if normalize_guard_symbol(raw_symbol) != normalized_symbol:
            continue
        pos_qty = _float(position.get("qty")) or 0.0
        market_value = _float(position.get("market_value"))
        if market_value is not None:
            position_notional = abs(market_value)
        elif price is not None:
            position_notional = abs(pos_qty * price)
        break

    pending_notional = 0.0
    prefix = client_order_id_prefix(fill_tag)
    for order in open_orders:
        cid = order.get("client_order_id")
        if not isinstance(cid, str) or not cid.startswith(prefix):
            continue
        raw_symbol = order.get("symbol")
        if not isinstance(raw_symbol, str):
            continue
        if normalize_guard_symbol(raw_symbol) != normalized_symbol:
            continue
        order_qty = _float(order.get("qty")) or 0.0
        filled = _float(order.get("filled_qty")) or 0.0
        remaining = max(order_qty - filled, 0.0)
        pending_notional += remaining * price

    new_notional = qty * price
    return position_notional + pending_notional + new_notional


def _reference_price_usd(hypothesis_id: str, intent: dict[str, Any]) -> float:
    ref = intent.get("reference_price_usd")
    if ref is not None:
        value = _float(ref)
        if value is not None and value > 0:
            return value
    events_path = repo_root() / "paper" / hypothesis_id / "forward" / "events.jsonl"
    if events_path.is_file():
        last_close: float | None = None
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event_type") != "signal":
                continue
            payload = event.get("payload")
            if isinstance(payload, dict):
                close = _float(payload.get("last_close"))
                if close is not None and close > 0:
                    last_close = close
        if last_close is not None:
            return last_close
    raise PaperAccountGuardError(
        "cannot estimate notional — set reference_price_usd on intent or record a forward signal"
    )


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
