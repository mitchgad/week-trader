from __future__ import annotations

from typing import Any

from week_trader.paper_forward import normalize_trading_symbol


def normalize_signal_side(signal: dict[str, Any]) -> str:
    side = signal.get("side")
    if not isinstance(side, str):
        return "flat"
    return side.strip().lower()


def signal_is_flat(signal: dict[str, Any]) -> bool:
    return normalize_signal_side(signal) == "flat"


def signal_matches_order_intent(
    signal: dict[str, Any],
    intent: dict[str, Any],
    *,
    signal_side: str | None = None,
) -> bool:
    """True when a forward signal agrees with a paper order intent (not for flat signals)."""
    side = signal_side if signal_side is not None else normalize_signal_side(signal)
    if side == "flat":
        return False
    intent_side = str(intent.get("side", "")).lower()
    symbol_raw = intent.get("symbol")
    if not isinstance(symbol_raw, str) or not symbol_raw.strip():
        return False
    intent_symbol = normalize_trading_symbol(symbol_raw)
    if side == "pairs":
        long_sym = signal.get("long_symbol")
        short_sym = signal.get("short_symbol")
        if intent_side == "buy" and isinstance(long_sym, str) and long_sym.strip():
            return normalize_trading_symbol(long_sym) == intent_symbol
        if intent_side == "sell" and isinstance(short_sym, str) and short_sym.strip():
            return normalize_trading_symbol(short_sym) == intent_symbol
        return False
    target = signal.get("target_symbol")
    if isinstance(target, str) and target.strip():
        if normalize_trading_symbol(target) != intent_symbol:
            return False
    if side == "long" and intent_side == "buy":
        return True
    if side == "short" and intent_side == "sell":
        return True
    return False
