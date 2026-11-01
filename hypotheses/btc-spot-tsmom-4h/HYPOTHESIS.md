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
| `allowed_symbols` | `BTC/USD` spot only (manifest universe) |

Alpaca paper **does not** simulate BTC perp funding, ADL, cross-margin, or mark-price liquidation ([grokbot-army.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/grokbot-army.md) §4.1; [Alpaca paper docs](https://docs.alpaca.markets/docs/paper-trading)). **Carry / funding** economics are a **different strategy class** from spot TSMOM ([research-gap-fill.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-gap-fill.md) §1 — BIS crypto carry vs daily momentum evidence).

## Validation and promotion proof

Operational proof for this hypothesis is **only** real-time **Alpaca paper crypto spot** forward tracking — not backtest replay, not Jesse parity runs, not external perp sims.

| Allowed proof | Forbidden as proof for this ID |
|---------------|--------------------------------|
| Alpaca paper **spot** fills and equity curve in `paper/btc-spot-tsmom-4h/forward/` + `journal/` | **Perp funding** accrual P&amp;L, Binance Futures testnet/mock, or any `crypto_perp` venue |
| `paper-forward` 4h signals on manifest `BTC/USD` with `closes_source=alpaca_live_4h` | Basis/carry or funding-harvest metrics (gap-fill §1; He et al. perp–spot frictions) |
| Signed Jev **trade** gate + `paper-order` intents bound to `BTCUSD` spot | Promoting from **engine-parity backtest** alone without paper forward bars |

Code enforcement (not narrative): manifest `instrument_class: crypto_spot` with `costs.funding_series_id: null`; `week_trader.manifest.validate_manifest_costs` rejects `crypto_perp` on `alpaca_paper`; `paper-order` rejects non-spot symbols and perp venue contracts. Intake memo: [docs/intake/btc-spot-tsmom-4h-venue-proof.md](../../docs/intake/btc-spot-tsmom-4h-venue-proof.md).

## Costs

Bound manifest `data/manifests/btc-spot-tsmom-4h-alpaca.yaml` (`costs.fee_bps_per_side`, `costs.slippage_bps_per_side`; **`funding_series_id` must stay null** for spot). **Gate 2 backtest** (engine parity + signed backtest gate) is for **kill/advance-to-paper diagnostics only** — backtest metrics **do not** satisfy Gate 3 operational proof. **Gate 3 proof** is Alpaca paper spot forward only (`proof_contract` in preregistration).

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
| Any promotion or “paper pass” argument cites **perp funding P&amp;L**, **Binance testnet perp**, or **carry/basis** results instead of Alpaca **spot** forward logs | **Venue-class violation** — falsifies the frozen `venue_contract`; kill immediately ([algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md) Part B §B.1). |

**Explicitly out of scope:** Mean-reversion z-score rules (gap-fill §2: BTC spot MR is **contested** — Turatti explosive / Corbet asymmetric dynamics); **perp funding, basis, or carry trades as evidence or as substitute instruments**; minute/session scalping.
