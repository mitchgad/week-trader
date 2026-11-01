# Hypothesis `eth-spot-tsmom-4h` (frozen spec — not traded until gates)

**Family:** Time-series momentum on **ETH/USD spot** (momentum literature; **not** mean reversion, not carry/funding, not equity pairs).

**Status:** Frozen spec for Jev and paper forward. **No edge claimed.** Short-horizon crypto momentum has **gross** support in multi-coin panels; **4h ETH spot net profitability is unproven** ([docs/intake/eth-spot-tsmom-4h-research.md](../../docs/intake/eth-spot-tsmom-4h-research.md)).

## Economic mechanism

Test whether **past ETH/USD spot returns** over a fixed formation window predict **same-direction** long-only exposure over the next **hours to several days**, after manifest fees and slippage on **Alpaca crypto spot**.

Motivation (not proof): Tzouvanas et al. (*Economics Letters*, [DOI 10.1016/j.econlet.2019.108728](https://doi.org/10.1016/j.econlet.2019.108728)) document **short-horizon cross-sectional momentum** across twelve cryptocurrencies with **fade at longer horizons**. Liu & Tsyvinski (NBER WP 24877, [https://www.nber.org/papers/w24877](https://www.nber.org/papers/w24877)) document **time-series momentum** in crypto factor panels on **daily** data. This spec is a **portability test** compressing TSMOM intuition to **4h ETH spot** — **not a production signal**.

## Universe and horizon

- **Universe:** ETH/USD **spot** only (single name; symbol other than BTC/USD).
- **Bar interval:** 4h UTC.
- **Hold:** Enter after signal at *t+1* open; hold up to **5 calendar days** (30 × 4h bars) or until signal flat, whichever first.

## Signal and timing

- **Formation:** Sum of log returns over the prior **6** completed 4h bars (24h lookback).
- **Signal at bar *t* close:** `long` if formation return > 0; `flat` otherwise (no short — spot constraint).
- **Order:** Next bar open after signal; no intrabar fills.
- **Exit:** Flat when formation return ≤ 0 at bar close, or max hold reached.

## Sizing and risk

- Long-only; notional capped by `paper_account_guards.json` strategy slice and `risk_limits.json`.
- Shared Alpaca paper account; **BTC/USD remains owned by `btc-spot-tsmom-4h`**.

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_crypto |
| `paper_venue` | alpaca_paper |
| `instrument_class` | crypto_spot |
| `allowed_symbols` | `ETH/USD` only |

Alpaca paper does **not** simulate perp funding, ADL, or cross-margin. **Carry/funding** is a **different strategy class** (see gap-fill §1).

## Validation and promotion proof

Operational proof is **Alpaca paper ETH spot forward** tracking only — not backtest replay or Jesse parity as Gate 3 proof.

| Allowed proof | Forbidden as proof |
|---------------|-------------------|
| Alpaca paper spot forward in `paper/eth-spot-tsmom-4h/forward/` | Perp funding P&amp;L, Binance testnet, basis/carry backtests |
| `paper-forward` 4h signals on manifest `ETH/USD` | Using BTC-only forward logs as ETH proof |

## Costs

Manifest `data/manifests/eth-spot-tsmom-4h-alpaca.yaml` — `funding_series_id` must stay **null** for spot.

## Kill conditions (algorithms A.6)

Same structure as project defaults: haircut OOS failure, 2× cost stress, horizon fade (Tzouvanas-style), implementation audit failure.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| OOS long-only TSMOM **underperforms** ETH buy-and-hold after identical costs | No gross structure at this horizon. |
| **2×** cost stress removes positive OOS mean return | Cost-dominated (gap-fill §1). |
| Signal **inverts** on OOS folds | Contradicts TSMOM direction — not MR rescue. |
| Promotion cites **perp funding**, **carry**, or **BTC-only** forward logs | Venue-class / symbol violation — kill. |

**Out of scope:** BTC spot mean reversion; equity pairs; funding harvest on this account.
