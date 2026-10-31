# Backtest engines (Phase 1)

Week trader uses a **deterministic primary golden-slice engine** plus an optional **MIT Jesse** second engine for §6.3 parity — not hypothesis strategies.

## Primary engine

`week_trader/engines/golden_slice.py` loads `week_trader/fixtures/golden_slice_1m.csv` and computes a buy-and-hold **net return** with manifest fee + slippage bps (infrastructure reference only).

## Jesse adapter (thin)

- API: `jesse.research.backtest` via `week_trader/jesse_isolated_runner.py`
- No vendored `jesse-ai/jesse` git tree, no freqtrade/Lean, no live stack
- Jesse PyPI pins conflict with main `pandas>=2`; install Jesse in a **separate venv** and set:

```bash
export JESSE_PYTHON=/path/to/jesse-venv/bin/python
make engine-parity ID=_template --write-run
```

Or run `engine-parity ID=_template --write-run` after parity passes to create `backtests/<id>/run-*/` with `metrics.json` and `engine_parity.json` for `make verify-backtest ID=`.

## Commands

```bash
make engine-parity ID=_template
make engine-parity ID=_template WRITE_RUN=1
make verify-backtest ID=_template
```

Gate 4 remains `blocked_v1`. No TypeSafe calls in engine code.
