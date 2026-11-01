# week-trader

Research → Jev-gated validation → paper trading. **v1: no live trading.**

Project specs live in the Week trader Project store (`docs/week-trader-plan.md`, `jev.md`, etc.). This repo is the executable scaffold only.

## Status (2026-11-02)

| Area | State |
|------|--------|
| Gate 4 / live trading | **Blocked** (`gates/gate4-checklist.yaml`, `make gate4-closed`) |
| Strategy validation | **Forward paper only** — `paper-forward` records signals, fills, and P&L from Alpaca paper; **`paper/` forward logs are the validation artifact**. Backtests (`backtests/`, engine parity) are research scaffolding — **never proof of edge** |
| Forward-paper hypotheses | Fourteen active frozen specs (shared Alpaca paper account); **`iwm-vol-overlay-1d` dropped** after spec-gate miss — no forward loop |
| Jev trade gate → order | On a matching non-flat signal, `paper-forward` runs **`jev-gate` trade** then **`paper-order` only if the signed log passes**; flat signals and intent mismatches never submit |
| Paper orders | `paper-order` requires a fresh signed **trade** gate, hypothesis `HALT` clear, **`paper_account_guards.json` + `config/paper_guards/`** (symbol owner, slice notional, opposite-order lock, account halt), and Alpaca **paper-api only** (`ALPACA_PAPER_KEY` / `ALPACA_PAPER_SECRET`) |
| Order tags | Alpaca `client_order_id` uses each slice **`fill_tag`** (`wt-<hypothesis-id>`); fills append to `paper/_shared/fill_tags.jsonl` |
| Jev gates | **Blocked in CI/agents** until `GATE_LOG_HMAC_SECRET` is injected (TypeSafe calls need `TYPESAFE_API_KEY` + HMAC to sign logs). No hand-written `gates/` JSON |
| Paper forward loop | `paper-forward ID=<hypothesis>` monitors account/orders; `ACTION=signal CLOSES=live` records the signal then may run trade gate + `paper-order`; `CHECK_ALERTS=1` writes `alerts.json` |
| Scheduled forward | GitHub Actions `paper-forward-schedule` (BTC 4h + hourly monitor) plus per-hypothesis `paper-forward-*.yml` workflows |

### Forward-paper hypotheses (2026-11-02)

One symbol owner per name on the shared paper account (`docs/runbooks/shared-paper-account.md`, `docs/intake/parked-strategies.md`).

| ID | Cadence / notes |
|----|-----------------|
| `btc-spot-tsmom-4h` | 4h crypto spot; legacy `paper-forward-schedule` |
| `eth-spot-tsmom-4h` | 4h crypto spot |
| `crypto-alts-csmom-4h` | 4h alt cross-section (long-only legs) |
| `spy-equity-tsmom-1d`, `dia-mean-reversion-1d`, `eem-xlf-csmom-1d` | Daily equity |
| `tlt-ief-pairs-1d`, `vgit-shy-term-carry-1d`, `vb-vv-size-spread-1d` | Daily pairs (long + short ETF legs on paper) |
| `gld-negative-attention-1d`, `slv-negative-attention-1d`, `mara-positive-attention-1d` | Daily attention / Trends |
| `qqq-volume-confirm-1d`, `xbi-max-short-1d` | Daily equity factor |

### Trade gate wiring (signal → paper fill)

1. **`paper-forward`** evaluates the frozen signal and appends to `paper/<id>/forward/events.jsonl`.
2. If the signal is **non-flat** and matches an order intent under `paper/<id>/intents/`, **`submit_paper_order_for_signal`** (`week_trader/paper_forward_order.py`) runs **`scripts/jev-gate` trade** (TypeSafe + signed log under `gates/<id>/`).
3. When the trade gate log has **`pass: true`**, **`paper-order`** validates the log hash, HALT, guards, and paper-api host, then submits with the strategy **`wt-…` fill tag** as `client_order_id`.
4. No chat, agent, or workflow path bypasses trade gate + guards; a failing gate returns **`trade_gate_did_not_pass`** with no broker call.

### How to run (local)

Forward paper (requires Alpaca paper secrets):

```bash
pip install -e ".[dev]"
make gate4-closed
paper-forward ID=btc-spot-tsmom-4h
paper-forward ID=btc-spot-tsmom-4h CHECK_ALERTS=1
paper-forward ID=btc-spot-tsmom-4h --dry-run
paper-forward ID=btc-spot-tsmom-4h ACTION=signal CLOSES=live
paper-forward ID=spy-equity-tsmom-1d ACTION=signal CLOSES=live
paper-forward ID=btc-spot-tsmom-4h ACTION=alerts
```

Events append to `paper/<id>/forward/events.jsonl`; latest snapshot in `status.json` (includes **`pnl_view`**, **`forward_evidence`** with PSR / MinTRL / deflated Sharpe vs ~14 running strategies, and **`not_enough_data_yet`** until MinTRL is met); anomaly report in `alerts.json`.

Research backtests (not validation — do not cite as edge):

```bash
make lint-jev-questions ID=btc-spot-tsmom-4h
make data-validate MANIFEST=data/manifests/btc-spot-tsmom-4h-alpaca.yaml
export JESSE_PYTHON=/path/to/python3.10-venv-with-jesse  # see docs/backtest-engines.md
make engine-parity ID=btc-spot-tsmom-4h
make verify-backtest ID=btc-spot-tsmom-4h
pytest -q
```

Signed Jev logs (after secrets are present):

```bash
make jev-gate ID=btc-spot-tsmom-4h GATE=spec
make jev-gate ID=btc-spot-tsmom-4h GATE=backtest METRICS=backtests/btc-spot-tsmom-4h/run-0001/metrics.json
make jev-gate ID=btc-spot-tsmom-4h GATE=trade
```

Commit signed logs only from `jev-gate` under `gates/<hypothesis-id>/` (gitignore exception added).

`build-jev-state ID=<hypothesis> GATE=<gate>` includes prereg spec fields and, when present, forward monitor snapshots (`data_fresh`, `within_risk_bands`, Alpaca paper `account_book` — equity, buying power, positions, open orders — and `last_signal_side`) for human Jev review — it does not call TypeSafe.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make lint-jev-questions ID=_template
make gate4-closed
```

Secrets (never commit): `TYPESAFE_API_KEY`, `GATE_LOG_HMAC_SECRET`, `ALPACA_PAPER_KEY`, `ALPACA_PAPER_SECRET`.
