# Hypothesis `iwm-vol-overlay-1d` (frozen spec — not traded until gates)

**Family:** Volatility-managed **long-only overlay** on slow **time-series momentum** for **IWM** daily bars (Moreira & Muir scaling on a Jegadeesh–Titman-style slow base). **Not** crypto TSMOM, not pairs, not carry.

**Status:** **Dropped** (2026-11-01). **Unproven** Moreira & Muir ([DOI 10.1111/jofi.12513](https://doi.org/10.1111/jofi.12513)) portability test — weight **σ*/realized vol** vs paper execution capped at **1.0× the strategy slice** (5000 USD). After the signal was aligned to that weight ( **`w_exec = min(w_t, 1.0)`** ), Jev **`vol_overlay_long_only_honest`** fell from **0.61** to **0.59** (below 0.65). **No paper-forward, no orders.** Signed gate logs remain under `gates/iwm-vol-overlay-1d/`.

## Paper long-only honesty (operational)

This hypothesis **honestly caps executed long exposure at 1.0× the strategy slice** (**5000 USD** max gross long on Alpaca paper). It **forbids short IWM** and **forbids any live broker endpoint**. The **signal** records Moreira **`w_t = sigma_star / rv_21`**; **orders** size with **`w_exec = min(w_t, 1.0)`** so paper execution never exceeds the slice cap.

## Moreira-Muir scaling (long-only, paper-bounded)

Moreira & Muir (*Journal of Finance*, 2017) scale managed exposure with **target volatility divided by realized volatility** (inverse-vol weighting). On a long-only IWM base:

| Rule | Value |
|------|--------|
| Overlay weight when `base_long` | **`w_t = sigma_star / rv_21`** (annualized σ* = 10%, `rv_21` from prior 21 daily returns) |
| Short IWM | **Forbidden** — when base not long, **`w_t = 0`** |
| Alpaca paper bounds (execution) | **`w_exec = min(w_t, 1.0)`** for order sizing against the **5000 USD** slice; **`w_t`** (Moreira) stored in forward signal payload. No live endpoints. |
| Short IWM | **Forbidden** |

When `rv_21` is near zero, treat **`w_t = sigma_star / max(rv_21, rv_floor)`** with **`rv_floor = 0.01`** (1% annualized) to avoid divide-by-zero; document in signal payload.

## Economic mechanism

When slow momentum on IWM is positive, hold long exposure scaled by **`w_t = sigma_star / rv_21`** (Moreira–Muir). When momentum is non-positive, **`w_t = 0`**. No short IWM.

## Universe and horizon

- **Universe:** `IWM` (US ETF, regular session).
- **Bar interval:** 1 trading day (Alpaca daily bars, NY calendar).
- **Rebalance:** Signal at daily bar *t* close; orders at next session open per manifest.

## Signal and timing (fixed parameters)

All features use data **≤ bar t close**; no lookahead.

### Base (slow TSMOM)

- `mom_12_1` = log(P_{t-21}/P_{t-252}) using **split-adjusted** daily closes (classic **12-1 month** skip of the most recent 21 sessions).
- **Base direction:** `base_long` if `mom_12_1` > 0; else flat.

### Realized volatility

- Daily log returns r_i = log(P_i/P_{i-1}) for i = t−20 … t.
- `rv_21` = sample std of those 21 daily log returns, annualized: `rv_21 * sqrt(252)`.

### Vol overlay (Moreira & Muir 2017)

- Target vol `sigma_star` = **0.10** (10% annualized).
- **`rv_floor`** = **0.01** (1% annualized minimum for division).
- When `base_long`: **`w_t = sigma_star / max(rv_21, rv_floor)`** — apply Moreira scaling directly (no hard ceiling at 100%).
- When not `base_long`: **`w_t = 0`**, **`w_exec = 0`**.

### Published side

- **`w_exec = min(w_t, 1.0)`** — **caps executed long exposure at 1.0× strategy slice** (Alpaca paper long-only; no margin lift on this ID).
- **`side` = `long`** if `w_exec >= 0.05`; else **`flat`**.
- Payload records `target_weight` (= `w_t`), `exec_weight` (= `w_exec`), `mom_12_1`, `rv_21_annualized`, `base_long`, `rv_floor`.

## Sizing and risk

- **Signal** follows Moreira **`w_t = sigma_star / max(rv_21, rv_floor)`**; **orders** size with **`w_exec`** so gross long notional **`≤ min(w_exec × slice_max, 5000 USD)`** with **`w_exec ≤ 1.0`**.
- Shared Alpaca paper account; **IWM owned only by `iwm-vol-overlay-1d`**.

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_equity |
| `paper_venue` | alpaca_paper |
| `instrument_class` | equity |
| `allowed_symbols` | `IWM` only |

Alpaca paper does **not** model hard-to-borrow or live locate for shorts; this spec **does not short**.

## Validation and promotion proof

Operational proof is **Alpaca paper IWM equity forward** tracking only — not backtest replay or Jesse parity as Gate 3 proof.

| Allowed proof | Forbidden as proof |
|---------------|-------------------|
| Alpaca paper forward in `paper/iwm-vol-overlay-1d/forward/` | Crypto perp funding, Binance testnet, BTC/ETH forward logs |
| `paper-forward` daily signals on manifest `IWM` | Backtest metrics as paper pass |

## Costs

Manifest `data/manifests/iwm-vol-overlay-1d-alpaca.yaml` — `funding_series_id` must stay **null** (equity spot/ETF).

## Kill conditions (algorithms A.6)

Haircut OOS failure (if backtest ever run), 2× cost stress, implementation audit failure, paper fail bars in Part B.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| Overlay **does not** reduce max drawdown vs unscaled base in OOS paper window (pre-registered) | Vol overlay adds no risk benefit — kill overlay variant. |
| **2×** slippage stress removes positive OOS mean return | Cost-dominated. |
| Promotion cites **perp funding**, **crypto carry**, or **BTC/ETH** forward logs | Venue/symbol violation — kill. |
| Orders exceed Alpaca paper **buying power** or strategy **slice** while claiming unconstrained Moreira leverage | Operational dishonesty — kill. |

**Out of scope:** BTC/ETH/SPY strategies; pairs; short IWM; live trading endpoints.
