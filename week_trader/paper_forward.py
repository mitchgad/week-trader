from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from week_trader.brokers.alpaca_paper import (
    AlpacaPaperError,
    fetch_crypto_4h_bar_closes,
    fetch_equity_daily_bar_closes,
    fetch_paper_account,
    fetch_paper_open_orders,
    fetch_paper_order,
    fetch_paper_positions,
)
from week_trader.attention.google_trends import GoogleTrendsError, fetch_daily_interest_pair
from week_trader.manifest import load_data_manifest, resolve_manifest_for_hypothesis
from week_trader.prereg import load_preregistration
from week_trader.strategies.gld_negative_attention_1d import evaluate_gld_negative_attention_1d
from week_trader.util import load_json, repo_root


class PaperForwardError(Exception):
    pass


FORWARD_STALE_STATUS_HOURS = 5.0


FetchAccount = Callable[..., dict[str, Any]]
FetchPositions = Callable[..., list[dict[str, Any]]]
FetchOpenOrders = Callable[..., list[dict[str, Any]]]
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


def manifest_trading_symbol(hypothesis_id: str) -> str:
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
    return symbol.strip()


def manifest_bar_interval(hypothesis_id: str) -> str:
    prereg = load_preregistration(hypothesis_id)
    manifest_path = resolve_manifest_for_hypothesis(hypothesis_id, prereg)
    manifest = load_data_manifest(manifest_path)
    bars = manifest.get("bars")
    if not isinstance(bars, dict):
        raise PaperForwardError("manifest bars missing")
    interval = bars.get("interval")
    if not isinstance(interval, str) or not interval.strip():
        raise PaperForwardError("manifest bars.interval missing")
    normalized = interval.strip()
    if normalized.lower() in {"1d", "1day"}:
        return "1Day"
    return normalized


def manifest_universe_symbols(hypothesis_id: str) -> list[str]:
    prereg = load_preregistration(hypothesis_id)
    manifest_path = resolve_manifest_for_hypothesis(hypothesis_id, prereg)
    manifest = load_data_manifest(manifest_path)
    universe = manifest.get("universe")
    if not isinstance(universe, dict):
        raise PaperForwardError("manifest universe missing")
    symbols = universe.get("symbols")
    if not isinstance(symbols, list) or len(symbols) < 1:
        raise PaperForwardError("manifest universe.symbols missing")
    out = [str(s).strip().upper() for s in symbols if isinstance(s, str) and s.strip()]
    if not out:
        raise PaperForwardError("manifest universe.symbols invalid")
    return out


def fetch_live_equity_daily_closes_map(hypothesis_id: str) -> dict[str, list[float]]:
    symbols = manifest_universe_symbols(hypothesis_id)
    closes_map: dict[str, list[float]] = {}
    try:
        for symbol in symbols:
            closes_map[symbol] = fetch_equity_daily_bar_closes(symbol, min_bars=30)
    except AlpacaPaperError as exc:
        raise PaperForwardError(str(exc)) from exc
    return closes_map


def manifest_crypto_symbol(hypothesis_id: str) -> str:
    symbol = manifest_trading_symbol(hypothesis_id)
    if manifest_bar_interval(hypothesis_id) != "4h":
        raise PaperForwardError("live 4h fetch requires manifest bars.interval 4h")
    return symbol


def fetch_live_4h_closes(hypothesis_id: str, *, min_bars: int = 8) -> list[float]:
    symbol = manifest_crypto_symbol(hypothesis_id)
    try:
        return fetch_crypto_4h_bar_closes(symbol, min_bars=min_bars)
    except AlpacaPaperError as exc:
        raise PaperForwardError(str(exc)) from exc


def fetch_live_equity_daily_closes(hypothesis_id: str, *, min_bars: int = 130) -> list[float]:
    symbol = manifest_trading_symbol(hypothesis_id)
    if manifest_bar_interval(hypothesis_id) != "1Day":
        raise PaperForwardError("live daily fetch requires manifest bars.interval 1Day")
    try:
        return fetch_equity_daily_bar_closes(symbol, min_bars=min_bars)
    except AlpacaPaperError as exc:
        raise PaperForwardError(str(exc)) from exc


def record_signal_from_live_bars(hypothesis_id: str) -> dict[str, Any]:
    prereg = load_preregistration(hypothesis_id)
    manifest_path = resolve_manifest_for_hypothesis(hypothesis_id, prereg)
    manifest = load_data_manifest(manifest_path)
    if hypothesis_id == "gld-negative-attention-1d":
        return record_gld_negative_attention_live_signal(hypothesis_id, manifest)
    interval = manifest_bar_interval(hypothesis_id)
    if interval == "1Day" and hypothesis_id == "eem-xlf-csmom-1d":
        closes_map = fetch_live_equity_daily_closes_map(hypothesis_id)
        signal = evaluate_eem_xlf_csmom_1d_signal(closes_map, hypothesis_id=hypothesis_id)
        signal["closes_source"] = "alpaca_live_1d"
        signal["symbols"] = list(closes_map.keys())
        signal["bar_count"] = min(len(v) for v in closes_map.values())
        return record_signal(hypothesis_id, signal)
    if interval == "1Day" and hypothesis_id == "tlt-ief-pairs-1d":
        closes_map = fetch_live_equity_daily_closes_map(hypothesis_id)
        signal = evaluate_tlt_ief_pairs_1d_signal(closes_map, hypothesis_id=hypothesis_id)
        signal["closes_source"] = "alpaca_live_1d"
        signal["symbols"] = list(closes_map.keys())
        signal["bar_count"] = min(len(v) for v in closes_map.values())
        return record_signal(hypothesis_id, signal)
    symbol = manifest_trading_symbol(hypothesis_id)
    if interval == "4h":
        closes = fetch_live_4h_closes(hypothesis_id)
        signal = evaluate_tsmom_4h_signal(closes, hypothesis_id=hypothesis_id)
        signal["closes_source"] = "alpaca_live_4h"
    elif interval == "1Day":
        closes = fetch_live_equity_daily_closes(hypothesis_id)
        signal = evaluate_equity_1d_signal(closes, hypothesis_id=hypothesis_id)
        signal["closes_source"] = "alpaca_live_1d"
    else:
        raise PaperForwardError(f"unsupported live bar interval {interval!r}")
    signal["symbol"] = symbol
    signal["bar_count"] = len(closes)
    return record_signal(hypothesis_id, signal)


def record_gld_negative_attention_live_signal(
    hypothesis_id: str, manifest: dict[str, Any]
) -> dict[str, Any]:
    attention = manifest.get("attention")
    if not isinstance(attention, dict):
        raise PaperForwardError("manifest attention block required for GLD attention signal")
    negative_kw = attention.get("negative_keyword")
    baseline_kw = attention.get("baseline_keyword")
    if not isinstance(negative_kw, str) or not isinstance(baseline_kw, str):
        raise PaperForwardError("manifest attention keywords required")
    lookback_rows = int(attention.get("lookback_rows", 252))
    high_q = float(attention.get("high_ratio_quantile", 0.8))
    symbol = _manifest_primary_symbol(manifest)
    try:
        trend_rows = fetch_daily_interest_pair(negative_kw, baseline_kw)
        daily_closes = fetch_equity_daily_bar_closes(symbol, min_bars=2)
    except (GoogleTrendsError, AlpacaPaperError) as exc:
        raise PaperForwardError(str(exc)) from exc
    signal = evaluate_gld_negative_attention_1d(
        trend_rows,
        hypothesis_id=hypothesis_id,
        lookback_rows=lookback_rows,
        high_ratio_quantile=high_q,
    )
    signal["closes_source"] = "google_trends_free_plus_alpaca_live_1d"
    signal["last_close"] = daily_closes[-1]
    signal["bar_count"] = len(daily_closes)
    return record_signal(hypothesis_id, signal)


def _manifest_primary_symbol(manifest: dict[str, Any]) -> str:
    universe = manifest.get("universe")
    if not isinstance(universe, dict):
        raise PaperForwardError("manifest universe missing")
    symbols = universe.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        raise PaperForwardError("manifest universe.symbols missing")
    symbol = symbols[0]
    if not isinstance(symbol, str) or not symbol.strip():
        raise PaperForwardError("manifest symbol invalid")
    return symbol.strip().upper()


def evaluate_tsmom_4h_signal(closes: list[float], *, hypothesis_id: str) -> dict[str, Any]:
    """
    4h TSMOM signal at bar close (formation = sum of log returns over prior 6 bars).
    Observation only — orders still require paper-order + trade gate.
    """
    formation_bars = 6
    if len(closes) < formation_bars + 1:
        raise PaperForwardError(f"need at least {formation_bars + 1} closes for tsmom signal")
    window = closes[-(formation_bars + 1) : -1]
    formation_log_return = sum(math.log(window[i] / window[i - 1]) for i in range(1, len(window)))
    side = "long" if formation_log_return > 0 else "flat"
    return {
        "strategy": hypothesis_id,
        "formation_bars": formation_bars,
        "formation_log_return": formation_log_return,
        "side": side,
        "last_close": closes[-1],
    }


def evaluate_dia_mean_reversion_1d_signal(closes: list[float], *, hypothesis_id: str) -> dict[str, Any]:
    """Daily contrarian loser leg: long when prior 5-day simple return is negative."""
    formation_days = 5
    if len(closes) < formation_days + 1:
        raise PaperForwardError(
            f"need at least {formation_days + 1} daily closes for {hypothesis_id} signal"
        )
    start_close = closes[-(formation_days + 1)]
    end_close = closes[-1]
    if start_close <= 0:
        raise PaperForwardError("invalid non-positive close in formation window")
    formation_return = end_close / start_close - 1.0
    side = "long" if formation_return < 0 else "flat"
    return {
        "strategy": hypothesis_id,
        "formation_days": formation_days,
        "formation_return": formation_return,
        "side": side,
        "last_close": end_close,
    }


def evaluate_eem_xlf_csmom_1d_signal(
    closes_by_symbol: dict[str, list[float]], *, hypothesis_id: str
) -> dict[str, Any]:
    """Long-only cross-sectional momentum on two ETFs: long relative winner."""
    formation_days = 21
    returns: dict[str, float] = {}
    for symbol, closes in closes_by_symbol.items():
        if len(closes) < formation_days + 1:
            raise PaperForwardError(f"need {formation_days + 1} closes for {symbol}")
        start = closes[-(formation_days + 1)]
        end = closes[-1]
        if start <= 0:
            raise PaperForwardError(f"invalid close for {symbol}")
        returns[symbol.upper()] = end / start - 1.0
    winner = max(returns, key=returns.get)
    return {
        "strategy": hypothesis_id,
        "formation_days": formation_days,
        "formation_returns": returns,
        "side": "long",
        "target_symbol": winner,
        "last_closes": {sym: closes_by_symbol[sym][-1] for sym in closes_by_symbol},
    }


def evaluate_tlt_ief_pairs_1d_signal(
    closes_by_symbol: dict[str, list[float]], *, hypothesis_id: str
) -> dict[str, Any]:
    """Distance-style spread z-score on log(TLT/IEF); convergence trade when |z| large."""
    lookback = 60
    entry_z = 2.0
    exit_z = 0.5
    tlt = closes_by_symbol.get("TLT")
    ief = closes_by_symbol.get("IEF")
    if tlt is None or ief is None:
        raise PaperForwardError("TLT and IEF closes required for pairs signal")
    if len(tlt) < lookback + 1 or len(ief) < lookback + 1:
        raise PaperForwardError(f"need {lookback + 1} daily closes for pairs z-score")
    ratios: list[float] = []
    for i in range(-lookback, 0):
        if tlt[i] <= 0 or ief[i] <= 0:
            raise PaperForwardError("non-positive close in pairs window")
        ratios.append(math.log(tlt[i] / ief[i]))
    current = ratios[-1]
    mean = sum(ratios) / len(ratios)
    var = sum((r - mean) ** 2 for r in ratios) / max(len(ratios) - 1, 1)
    std = math.sqrt(var) if var > 0 else 0.0
    spread_z = (current - mean) / std if std > 0 else 0.0
    if abs(spread_z) <= exit_z:
        return {
            "strategy": hypothesis_id,
            "side": "flat",
            "spread_z": spread_z,
            "lookback_days": lookback,
        }
    if spread_z > entry_z:
        return {
            "strategy": hypothesis_id,
            "side": "pairs",
            "long_symbol": "IEF",
            "short_symbol": "TLT",
            "spread_z": spread_z,
            "lookback_days": lookback,
        }
    if spread_z < -entry_z:
        return {
            "strategy": hypothesis_id,
            "side": "pairs",
            "long_symbol": "TLT",
            "short_symbol": "IEF",
            "spread_z": spread_z,
            "lookback_days": lookback,
        }
    return {
        "strategy": hypothesis_id,
        "side": "flat",
        "spread_z": spread_z,
        "lookback_days": lookback,
        "note": "inside entry band",
    }


IWM_MOM_LONG_OFFSET = 252
IWM_MOM_SKIP_RECENT = 21
IWM_RV_WINDOW = 21
IWM_SIGMA_STAR = 0.10
IWM_RV_FLOOR = 0.01
IWM_DUST_WEIGHT = 0.05


def evaluate_iwm_vol_overlay_signal(closes: list[float], *, hypothesis_id: str) -> dict[str, Any]:
    """Daily IWM vol-managed overlay: Moreira-Muir w_t = sigma_star / rv (long-only base)."""
    min_needed = IWM_MOM_LONG_OFFSET + IWM_MOM_SKIP_RECENT + 2
    if len(closes) < min_needed:
        raise PaperForwardError(
            f"need at least {min_needed} daily closes for iwm vol overlay; got {len(closes)}"
        )
    mom_12_1 = math.log(closes[-1 - IWM_MOM_SKIP_RECENT] / closes[-1 - IWM_MOM_LONG_OFFSET])
    base_long = mom_12_1 > 0.0
    rv_window = closes[-(IWM_RV_WINDOW + 1) :]
    daily_logs = [math.log(rv_window[i] / rv_window[i - 1]) for i in range(1, len(rv_window))]
    if len(daily_logs) < IWM_RV_WINDOW:
        raise PaperForwardError("insufficient daily returns for realized vol")
    mean = sum(daily_logs) / len(daily_logs)
    var = sum((x - mean) ** 2 for x in daily_logs) / max(len(daily_logs) - 1, 1)
    rv_21 = math.sqrt(var) * math.sqrt(252.0)
    target_weight = 0.0
    if base_long:
        rv_eff = max(rv_21, IWM_RV_FLOOR)
        target_weight = max(0.0, IWM_SIGMA_STAR / rv_eff)
    exec_weight = min(target_weight, 1.0)
    side = "long" if exec_weight >= IWM_DUST_WEIGHT else "flat"
    return {
        "strategy": hypothesis_id,
        "side": side,
        "target_weight": target_weight,
        "exec_weight": exec_weight,
        "base_long": base_long,
        "mom_12_1": mom_12_1,
        "rv_21_annualized": rv_21,
        "rv_floor": IWM_RV_FLOOR,
        "sigma_star": IWM_SIGMA_STAR,
        "last_close": closes[-1],
    }


def evaluate_equity_1d_signal(closes: list[float], *, hypothesis_id: str) -> dict[str, Any]:
    if hypothesis_id == "dia-mean-reversion-1d":
        return evaluate_dia_mean_reversion_1d_signal(closes, hypothesis_id=hypothesis_id)
    if hypothesis_id == "iwm-vol-overlay-1d":
        return evaluate_iwm_vol_overlay_signal(closes, hypothesis_id=hypothesis_id)
    return evaluate_tsmom_1d_signal(closes, hypothesis_id=hypothesis_id)


def evaluate_tsmom_1d_signal(closes: list[float], *, hypothesis_id: str) -> dict[str, Any]:
    """
    Daily TSMOM signal at session close (formation = sum of log returns over prior 126 sessions).
    Observation only — orders still require paper-order + trade gate.
    """
    formation_bars = 126
    if len(closes) < formation_bars + 1:
        raise PaperForwardError(f"need at least {formation_bars + 1} closes for tsmom signal")
    window = closes[-(formation_bars + 1) : -1]
    formation_log_return = sum(math.log(window[i] / window[i - 1]) for i in range(1, len(window)))
    side = "long" if formation_log_return > 0 else "flat"
    return {
        "strategy": hypothesis_id,
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
    fetch_open_orders: FetchOpenOrders | None = None,
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
    get_open_orders = fetch_open_orders or fetch_paper_open_orders
    get_order = fetch_order or fetch_paper_order

    try:
        account = get_account()
        positions = get_positions()
        open_orders = get_open_orders()
    except AlpacaPaperError as exc:
        raise PaperForwardError(str(exc)) from exc

    synced_utc = _utc_now()
    account_book = build_paper_account_book(
        account,
        positions,
        open_orders,
        synced_utc=synced_utc,
    )

    fills_synced = _sync_pending_orders(hypothesis_id, get_order)
    pnl = _pnl_snapshot(account, positions)
    btc_spot_position: dict[str, Any] | None = None
    try:
        manifest_symbol = manifest_trading_symbol(hypothesis_id)
        prereg = load_preregistration(hypothesis_id)
        manifest_path = resolve_manifest_for_hypothesis(hypothesis_id, prereg)
        manifest = load_data_manifest(manifest_path)
        if manifest.get("instrument_class") in {"equity", "equity_etf"}:
            btc_spot_position = summarize_equity_position(positions, manifest_symbol)
        else:
            btc_spot_position = summarize_spot_position(positions, manifest_symbol)
    except PaperForwardError:
        btc_spot_position = None
    append_forward_event(hypothesis_id, "pnl_snapshot", pnl)
    for fill in fills_synced:
        append_forward_event(hypothesis_id, "fill", fill)

    status = {
        "hypothesis_id": hypothesis_id,
        "timestamp_utc": synced_utc,
        "account_equity": pnl.get("equity"),
        "last_equity": pnl.get("last_equity"),
        "cash": pnl.get("cash"),
        "buying_power": pnl.get("buying_power"),
        "unrealized_pl": pnl.get("unrealized_pl"),
        "open_positions": len(positions),
        "open_order_count": account_book["open_order_count"],
        "account_book": account_book,
        "fills_synced_this_tick": len(fills_synced),
        "validation_mode": "forward_paper_only",
    }
    if btc_spot_position is not None:
        status["btc_spot_position"] = btc_spot_position
    last_signal_side = read_last_signal_side(forward_dir(hypothesis_id) / "events.jsonl")
    if last_signal_side is not None:
        status["last_signal_side"] = last_signal_side
    _write_status(hypothesis_id, status)
    return status


def run_forward_monitor_with_alerts(
    hypothesis_id: str,
    *,
    dry_run: bool = False,
    fetch_account: FetchAccount | None = None,
    fetch_positions: FetchPositions | None = None,
    fetch_open_orders: FetchOpenOrders | None = None,
    fetch_order: FetchOrder | None = None,
) -> dict[str, Any]:
    from week_trader.forward_anomalies import check_forward_anomalies

    status = run_forward_monitor_tick(
        hypothesis_id,
        dry_run=dry_run,
        fetch_account=fetch_account,
        fetch_positions=fetch_positions,
        fetch_open_orders=fetch_open_orders,
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


def build_paper_account_book(
    account: dict[str, Any],
    positions: list[dict[str, Any]],
    open_orders: list[dict[str, Any]],
    *,
    synced_utc: str,
) -> dict[str, Any]:
    """Structured Alpaca paper account book for forward status and Jev state."""
    position_rows = [_summarize_book_position(p) for p in positions]
    order_rows = [_summarize_book_order(o) for o in open_orders]
    gross_exposure = sum(abs(row.get("market_value") or 0.0) for row in position_rows)
    return {
        "source": "alpaca_paper",
        "synced_utc": synced_utc,
        "equity": _float_or_none(account.get("equity")),
        "cash": _float_or_none(account.get("cash")),
        "buying_power": _float_or_none(account.get("buying_power")),
        "last_equity": _float_or_none(account.get("last_equity")),
        "position_count": len(position_rows),
        "open_order_count": len(order_rows),
        "gross_exposure_usd": gross_exposure,
        "positions": position_rows,
        "open_orders": order_rows,
    }


def _summarize_book_position(position: dict[str, Any]) -> dict[str, Any]:
    qty = _float_or_none(position.get("qty")) or 0.0
    return {
        "symbol": position.get("symbol"),
        "qty": qty,
        "market_value": _float_or_none(position.get("market_value")),
        "side": position.get("side"),
        "open": qty != 0.0,
    }


def _summarize_book_order(order: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": order.get("id"),
        "symbol": order.get("symbol"),
        "side": order.get("side"),
        "qty": order.get("qty"),
        "status": order.get("status"),
        "type": order.get("type"),
    }


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


def normalize_alpaca_crypto_symbol(symbol: str) -> str:
    return symbol.replace("/", "").upper()


def normalize_trading_symbol(symbol: str) -> str:
    cleaned = symbol.strip().upper()
    if "/" in cleaned:
        return normalize_alpaca_crypto_symbol(cleaned)
    return cleaned


def summarize_spot_position(positions: list[dict[str, Any]], manifest_symbol: str) -> dict[str, Any]:
    target = normalize_trading_symbol(manifest_symbol)
    for position in positions:
        raw_symbol = position.get("symbol")
        if not raw_symbol:
            continue
        if normalize_trading_symbol(str(raw_symbol)) != target:
            continue
        qty = _float_or_none(position.get("qty")) or 0.0
        market_value = _float_or_none(position.get("market_value"))
        return {
            "symbol": str(raw_symbol),
            "qty": qty,
            "market_value": market_value,
            "open": qty > 0,
        }
    return {
        "symbol": manifest_symbol,
        "qty": 0.0,
        "market_value": 0.0,
        "open": False,
    }


def summarize_equity_position(positions: list[dict[str, Any]], symbol: str) -> dict[str, Any]:
    target = symbol.strip().upper()
    for position in positions:
        raw_symbol = position.get("symbol")
        if not raw_symbol:
            continue
        if str(raw_symbol).strip().upper() != target:
            continue
        qty = _float_or_none(position.get("qty")) or 0.0
        market_value = _float_or_none(position.get("market_value"))
        return {
            "symbol": str(raw_symbol),
            "qty": qty,
            "market_value": market_value,
            "open": qty > 0,
        }
    return {
        "symbol": symbol,
        "qty": 0.0,
        "market_value": 0.0,
        "open": False,
    }


def read_last_signal_side(events_path: Path) -> str | None:
    if not events_path.is_file():
        return None
    last_side: str | None = None
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
        if not isinstance(payload, dict):
            continue
        side = payload.get("side")
        if side in {"long", "flat"}:
            last_side = str(side)
    return last_side
