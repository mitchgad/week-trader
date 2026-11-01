# Hypothesis `iwm-vol-overlay-1d` (frozen spec — not traded until gates)

**Family:** Volatility-managed **long-only overlay** on slow **time-series momentum** for **IWM** daily bars (Moreira & Muir scaling on a Jegadeesh–Titman-style slow base). **Not** crypto TSMOM, not pairs, not carry.

**Status:** Frozen spec for Jev and paper forward. **No edge claimed.** Daily IWM vol overlay is an **unproven portability test** of Moreira & Muir ([DOI 10.1111/jofi.12513](https://doi.org/10.1111/jofi.12513)) — **not** a production signal and **not** the paper’s full factor leverage implementation.

## Long-only and leverage (honest Moreira adaptation)

Moreira & Muir scale **factor** exposure with leverage in-sample. This hypothesis **does not** replicate that leverage:

| Rule | Value |
|------|--------|
| Short IWM | **Forbidden** — base is long or flat only |
| Max gross long weight | **1.0** (100% of strategy slice) |
| Min gross long weight when `base_long` | **0.0** (may scale down in high vol) |
| Leverage above 100% long | **Forbidden** on Alpaca paper |
| Vol target `sigma_star` | 10% annualized; weight = `min(1.0, sigma_star / rv_21)` |

If realized vol is near zero, weight defaults to **1.0** (still capped — no extra leverage).

## Economic mechanism

When slow momentum on IWM is positive, hold a **fractional long** sized by inverse recent realized volatility (capped at 100% of the strategy slice). When momentum is non-positive, remain **flat**. No short IWM.

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

### Vol overlay (long-only)

- Target vol `sigma_star` = **0.10** (10% annualized).
- Raw weight `w_raw` = `sigma_star / rv_21` when `base_long`; else 0.
- **Target weight** `w = min(1.0, max(0.0, w_raw))` — **no leverage above 1.0**, no short.

### Published side

- **`side` = `long`** if `w >= 0.05`; else **`flat`** (dust band avoids churn).
- Payload records `target_weight`, `mom_12_1`, `rv_21_annualized`, `base_long`.

## Sizing and risk

- Long-only; max gross notional = `min(slice_max, w * slice_max)` with slice from merged paper guards (**5000 USD** for this ID).
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
| Spec requires **short IWM** or **leverage > 1.0** to match Moreira–Muir full factor scaling | Design dishonesty — kill (this spec forbids both). |

**Out of scope:** BTC/ETH/SPY strategies; pairs; margin beyond long-only cap.
