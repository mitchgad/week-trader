"""
Run in a Jesse-compatible interpreter (optional `JESSE_PYTHON` venv).

Uses `jesse.research.backtest` only — no Jesse project tree, routes repo, or live stack.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _parity_hold_strategy_class():
    from jesse.strategies import Strategy

    class ParityHoldInfrastructure(Strategy):
        """Infrastructure-only: enter long once on bar 1, hold (not a hypothesis strategy)."""

        def should_long(self) -> bool:
            return self.index == 1

        def should_cancel_entry(self) -> bool:
            return False

        def go_long(self) -> None:
            self.buy = 1, self.price

    return ParityHoldInfrastructure


def run_from_payload(payload: dict) -> dict[str, object]:
    import jesse.helpers as jh
    from jesse import research
    from jesse.factories import candles_from_close_prices

    closes = [float(x) for x in payload["closes"]]
    fee = float(payload["fee_rate"])
    exchange = str(payload.get("exchange", "Sandbox"))
    symbol = str(payload.get("symbol", "BTC-USDT"))

    candle_arr = candles_from_close_prices(closes)
    config = {
        "starting_balance": float(payload.get("starting_balance", 10_000)),
        "fee": fee,
        "type": "spot",
        "exchange": exchange,
        "warm_up_candles": 0,
    }
    strategy_cls = _parity_hold_strategy_class()
    routes = [
        {
            "exchange": exchange,
            "strategy": strategy_cls,
            "symbol": symbol,
            "timeframe": "1m",
        }
    ]
    candles = {
        jh.key(exchange, symbol): {
            "exchange": exchange,
            "symbol": symbol,
            "candles": candle_arr,
        }
    }
    result = research.backtest(config, routes, [], candles)
    metrics = result.get("metrics") or {}
    net_pct = float(metrics.get("net_profit_percentage") or 0.0) / 100.0
    return {
        "engine": "jesse_research_backtest",
        "net_return": net_pct,
        "jesse_metrics": metrics,
    }


def main(argv: list[str] | None = None) -> None:
    args = argv or sys.argv[1:]
    if len(args) != 1:
        raise SystemExit("usage: python -m week_trader.jesse_isolated_runner <payload.json>")
    payload_path = Path(args[0])
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    out = run_from_payload(payload)
    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
