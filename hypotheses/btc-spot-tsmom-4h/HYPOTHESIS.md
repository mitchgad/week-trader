# Hypothesis `btc-spot-tsmom-4h` (spec only — not traded)

**Family:** Time-series momentum on **BTC spot** (adapted from daily factor evidence; not a perp carry or MR spec).

**Status:** Draft spec for human freeze. **No edge claimed.** Literature supports gross daily BTC momentum in some samples; net profitability at this bar size is **unproven** ([research-gap-fill.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-gap-fill.md) §1).

## Economic mechanism

Test whether **past BTC spot returns** over a fixed formation window predict **same-direction** exposure over the next **hours to several days**, after fees and slippage on **Alpaca crypto spot**.

Motivation (not proof): Liu & Tsyvinski document **time-series momentum** in crypto factors on **daily** CoinDesk BTC samples (NBER WP 24877); Tzouvanas et al. find **short-horizon** cross-sectional momentum in crypto that **weakens at longer horizons** (Economics Letters 2020). This spec **compresses** daily TSMOM intuition to **4h bars** and **long-only spot** — a **portability test**, not a production signal.

## Universe and horizon

- **Universe:** BTC/USD **spot** only (single name).
- **Bar interval:** 4h UTC (not minute scalping).
- **Hold:** Enter after signal at *t+1* open; hold up to **5 calendar days** (30 × 4h bars) or until signal flat, whichever first.

## Signal and timing

- **Formation:** Sum of log returns over the prior **6** completed 4h bars (24h lookback).
- **Signal at bar *t* close:** `long` if formation return > 0; `flat` otherwise (no short — spot constraint).
- **Order:** Default **next bar open** after signal; no intrabar fills.
- **Exit:** Flat when formation return ≤ 0 at bar close, or max hold reached.

## Sizing and risk

- Long-only; max notional per `risk_limits.json` and preregistration caps.
- No leverage beyond cash spot exposure.

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_crypto |
| `paper_venue` | alpaca_paper (equities + **crypto spot sim only**) |
| `instrument_class` | crypto_spot |

Alpaca paper **does not** simulate BTC perp funding, ADL, cross-margin, or mark-price liquidation. This hypothesis **must not** be promoted using perp or testnet P&amp;L as proof.

## Costs

Bound manifest `data/manifests/btc-spot-tsmom-4h-alpaca.yaml` (`costs.fee_bps_per_side`, `costs.slippage_bps_per_side`). Backtest and promotion require **engine parity** per preregistration before metrics count.

## Kill conditions (algorithms A.6 — pre-registered)

Archive (kill ledger) if on concatenated OOS / walk-forward paths:

1. Haircut-adjusted OOS Sharpe or profit factor **below** preregistered hurdle given trial count **N**.
2. Net return **≤ 0** after manifest costs on OOS window with **≥ 20** round-trips, **or** economic result **vanishes** under **2×** cost stress (gap-fill §1).
3. **Horizon fade:** OOS performance **concentrated** in a single subperiod **or** sign **flips** across adjacent OOS folds without a pre-specified regime switch (Tzouvanas-style fade at longer horizons).
4. **Implementation audit** finds lookahead, bar timing mismatch, or fill rule violation.

## Disconfirmers (falsify the mechanism — not “bad luck”)

These outcomes **falsify** treating 4h BTC spot TSMOM as supported for this spec:

| Disconfirmer | Interpretation |
|--------------|----------------|
| OOS long-only TSMOM **underperforms** buy-and-hold BTC spot on the same bars after **identical** cost model | Momentum overlay adds no gross structure at this horizon. |
| **2×** fee + slippage stress removes all positive OOS mean return | Effect is cost-dominated (gap-fill §1: gross ≠ net). |
| Signal **inverts** (long formation predicts **lower** next-period return) with pre-registered statistical threshold on OOS folds | Contradicts TSMOM direction; kill — not MR rescue. |
| Performance exists **only** in one OOS month and **fails** adjacent folds | Unstable / overfit; contradicts portable daily literature adaptation. |
| Liu-style **daily** momentum ranks **disagree** with 4h signal on held-out calendar (pre-registered correlation / sign test fails) | Bar-size portability disconfirmed (daily evidence does not extend to 4h). |

**Explicitly out of scope:** Mean-reversion z-score rules (gap-fill §2: BTC spot MR is **contested** — Turatti explosive / Corbet asymmetric dynamics); perp funding or basis trades; minute/session scalping.
