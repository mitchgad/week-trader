# week-trader

Research → Jev-gated validation → paper trading. **v1: no live trading.**

Project specs live in the Week trader Project store (`docs/week-trader-plan.md`, `jev.md`, etc.). This repo is the executable scaffold only.

## Status (2026-10-31)

| Area | State |
|------|--------|
| Gate 4 / live trading | **Blocked** (`gates/gate4-checklist.yaml`, `make gate4-closed`) |
| Hypothesis `btc-spot-tsmom-4h` | Frozen spec + manifest; **engine parity run** under `backtests/btc-spot-tsmom-4h/run-0001/` |
| Jev gates | **Blocked in CI/agents** until `GATE_LOG_HMAC_SECRET` is injected (TypeSafe calls need `TYPESAFE_API_KEY` + HMAC to sign logs). No hand-written `gates/` JSON. |
| Paper orders | `paper-order` validates trade gate + HALT; Alpaca **paper-api only** (`ALPACA_PAPER_KEY` / `ALPACA_PAPER_SECRET`) |
| Full 4h TSMOM strategy backtest | **Not implemented** — current run is golden-slice **infrastructure parity** (primary vs Jesse hold), per [docs/backtest-engines.md](docs/backtest-engines.md) |

### How to run (local)

```bash
pip install -e ".[dev]"
make gate4-closed
make lint-jev-questions ID=btc-spot-tsmom-4h
make data-validate MANIFEST=data/manifests/btc-spot-tsmom-4h-alpaca.yaml
export JESSE_PYTHON=/path/to/python3.10-venv-with-jesse  # see docs/backtest-engines.md
make engine-parity ID=btc-spot-tsmom-4h
make engine-parity ID=btc-spot-tsmom-4h WRITE_RUN=1
make verify-backtest ID=btc-spot-tsmom-4h
pytest -q
```

Signed Jev logs (after secrets are present):

```bash
make jev-gate ID=btc-spot-tsmom-4h GATE=spec
make jev-gate ID=btc-spot-tsmom-4h GATE=backtest METRICS=backtests/btc-spot-tsmom-4h/run-0001/metrics.json
```

Commit signed logs only from `jev-gate` under `gates/btc-spot-tsmom-4h/` (gitignore exception added).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make lint-jev-questions ID=_template
make gate4-closed
```

Secrets (never commit): `TYPESAFE_API_KEY`, `GATE_LOG_HMAC_SECRET`, `ALPACA_PAPER_KEY`, `ALPACA_PAPER_SECRET`.
