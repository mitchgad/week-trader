from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from week_trader.brokers.alpaca_paper import (
    AlpacaPaperError,
    fetch_crypto_4h_bar_closes,
    fetch_paper_account,
    fetch_paper_order,
    fetch_paper_positions,
)
from week_trader.manifest import load_data_manifest, resolve_manifest_for_hypothesis
from week_trader.prereg import load_preregistration
from week_trader.util import load_json, repo_root


class PaperForwardError(Exception):
    pass


FetchAccount = Callable[..., dict[str, Any]]
FetchPositions = Callable[..., list[dict[str, Any]]]
FetchOrder = Callable[..., dict[str, Any]]


def forward_dir(hypothesis_id: str) -> Path:
    return repo_root() / "paper" / hypothesis_id / "forward"


def append_forward_event(hypothesis_id: str, event_type: str, payload: dict[str, Any]) -> Path:
    directory = forward_dir(hypothesis_id)
    directory.mkdir(parents=True, exist_ok=True)
    event = {
        "event_type": event_type,
        "timestamp_utc": _utc_now(),
        "hypothesis_id": hypothesis_id,
        "payload": payload,
    }
    path = directory / "events.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return path


def register_pending_order(hypothesis_id: str, order_id: str, meta: dict[str, Any]) -> None:
    directory = forward_dir(hypothesis_id)
    directory.mkdir(parents=True, exist_ok=True)
    pending_path = directory / "pending_orders.json"
    pending: dict[str, Any] = {}
    if pending_path.is_file():
        loaded = load_json(pending_path)
        if isinstance(loaded, dict):
            pending = loaded
    pending[order_id] = {**meta, "registered_at_utc": _utc_now()}
    pending_path.write_text(json.dumps(pending, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def record_signal(hypothesis_id: str, signal: dict[str, Any]) -> dict[str, Any]:
    """Record a strategy signal for forward validation (does not submit orders)."""
    append_forward_event(hypothesis_id, "signal", signal)
    return {"recorded": True, "signal": signal}


def manifest_crypto_symbol(hypothesis_id: str) -> str:
    prereg = load_preregistration(hypothesis_id)
    manifest_path = resolve_manifest_for_hypothesis(hypothesis_id, prereg)
    manifest = load_data_manifest(manifest_path)
    universe = manifest.get("universe")
    if not isinstance(universe, dict):
        raise PaperForwardError("manifest universe missing")
    symbols = universe.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        raise PaperForwardError("manifest universe.symbols missing")
    symbol = symbols[0]
    if not isinstance(symbol, str) or not symbol.strip():
        raise PaperForwardError("manifest symbol invalid")
    bars = manifest.get("bars")
    if isinstance(bars, dict) and bars.get("interval") != "4h":
        raise PaperForwardError("live 4h fetch requires manifest bars.interval 4h")
    return symbol.strip()


def fetch_live_4h_closes(hypothesis_id: str, *, min_bars: int = 8) -> list[float]:
    symbol = manifest_crypto_symbol(hypothesis_id)
    try:
        return fetch_crypto_4h_bar_closes(symbol, min_bars=min_bars)
    except AlpacaPaperError as exc:
        raise PaperForwardError(str(exc)) from exc


def record_signal_from_live_bars(hypothesis_id: str) -> dict[str, Any]:
    symbol = manifest_crypto_symbol(hypothesis_id)
    closes = fetch_live_4h_closes(hypothesis_id)
    signal = evaluate_tsmom_4h_signal(closes)
    signal["closes_source"] = "alpaca_live_4h"
    signal["symbol"] = symbol
    signal["bar_count"] = len(closes)
    return record_signal(hypothesis_id, signal)


def evaluate_tsmom_4h_signal(closes: list[float]) -> dict[str, Any]:
    """
    btc-spot-tsmom-4h signal at bar close (formation = sum of log returns over prior 6 bars).
    Observation only — orders still require paper-order + trade gate.
    """
    formation_bars = 6
    if len(closes) < formation_bars + 1:
        raise PaperForwardError(f"need at least {formation_bars + 1} closes for tsmom signal")
    window = closes[-(formation_bars + 1) : -1]
    formation_log_return = sum(math.log(window[i] / window[i - 1]) for i in range(1, len(window)))
    side = "long" if formation_log_return > 0 else "flat"
    return {
        "strategy": "btc-spot-tsmom-4h",
        "formation_bars": formation_bars,
        "formation_log_return": formation_log_return,
        "side": side,
        "last_close": closes[-1],
    }


def run_forward_monitor_tick(
    hypothesis_id: str,
    *,
    fetch_account: FetchAccount | None = None,
    fetch_positions: FetchPositions | None = None,
    fetch_order: FetchOrder | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    One paper-loop tick: sync pending orders, snapshot account P&L, append forward events.
    Strategy proof is forward paper tracking only (not backtests).
    """
    root = repo_root()
    halt_path = root / "paper" / hypothesis_id / "HALT"
    if halt_path.exists():
        raise PaperForwardError("HALT present — paper loop halted")

    if dry_run:
        status = {
            "hypothesis_id": hypothesis_id,
            "timestamp_utc": _utc_now(),
            "dry_run": True,
            "status": "halt_check_ok",
        }
        _write_status(hypothesis_id, status)
        return status

    get_account = fetch_account or fetch_paper_account
    get_positions = fetch_positions or fetch_paper_positions
    get_order = fetch_order or fetch_paper_order

    try:
        account = get_account()
        positions = get_positions()
    except AlpacaPaperError as exc:
        raise PaperForwardError(str(exc)) from exc

    fills_synced = _sync_pending_orders(hypothesis_id, get_order)
    pnl = _pnl_snapshot(account, positions)
    append_forward_event(hypothesis_id, "pnl_snapshot", pnl)
    for fill in fills_synced:
        append_forward_event(hypothesis_id, "fill", fill)

    status = {
        "hypothesis_id": hypothesis_id,
        "timestamp_utc": _utc_now(),
        "account_equity": pnl.get("equity"),
        "unrealized_pl": pnl.get("unrealized_pl"),
        "open_positions": len(positions),
        "fills_synced_this_tick": len(fills_synced),
        "validation_mode": "forward_paper_only",
    }
    _write_status(hypothesis_id, status)
    return status


def run_forward_monitor_with_alerts(
    hypothesis_id: str,
    *,
    dry_run: bool = False,
    fetch_account: FetchAccount | None = None,
    fetch_positions: FetchPositions | None = None,
    fetch_order: FetchOrder | None = None,
) -> dict[str, Any]:
    from week_trader.forward_anomalies import check_forward_anomalies

    status = run_forward_monitor_tick(
        hypothesis_id,
        dry_run=dry_run,
        fetch_account=fetch_account,
        fetch_positions=fetch_positions,
        fetch_order=fetch_order,
    )
    alerts = check_forward_anomalies(hypothesis_id)
    return {**status, "anomaly_severity": alerts.get("severity"), "anomaly_count": alerts.get("alert_count")}


def _sync_pending_orders(hypothesis_id: str, get_order: FetchOrder) -> list[dict[str, Any]]:
    directory = forward_dir(hypothesis_id)
    pending_path = directory / "pending_orders.json"
    if not pending_path.is_file():
        return []
    pending = load_json(pending_path)
    if not isinstance(pending, dict):
        return []

    fills: list[dict[str, Any]] = []
    remaining: dict[str, Any] = {}
    for order_id, meta in pending.items():
        try:
            order = get_order(order_id)
        except AlpacaPaperError:
            remaining[order_id] = meta
            continue
        status = str(order.get("status", "")).lower()
        if status in {"filled", "partially_filled"}:
            fills.append(
                {
                    "order_id": order_id,
                    "status": status,
                    "symbol": order.get("symbol"),
                    "filled_qty": order.get("filled_qty"),
                    "filled_avg_price": order.get("filled_avg_price"),
                    "meta": meta,
                }
            )
            if status == "partially_filled":
                remaining[order_id] = meta
        elif status in {"new", "accepted", "pending_new"}:
            remaining[order_id] = meta
        else:
            fills.append({"order_id": order_id, "status": status, "terminal": True, "meta": meta})

    pending_path.write_text(json.dumps(remaining, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return fills


def _pnl_snapshot(account: dict[str, Any], positions: list[dict[str, Any]]) -> dict[str, Any]:
    equity = _float_or_none(account.get("equity"))
    last_equity = _float_or_none(account.get("last_equity"))
    unrealized = sum(_float_or_none(p.get("unrealized_pl")) or 0.0 for p in positions)
    return {
        "equity": equity,
        "last_equity": last_equity,
        "cash": _float_or_none(account.get("cash")),
        "buying_power": _float_or_none(account.get("buying_power")),
        "unrealized_pl": unrealized,
        "position_count": len(positions),
    }


def _write_status(hypothesis_id: str, status: dict[str, Any]) -> None:
    directory = forward_dir(hypothesis_id)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
