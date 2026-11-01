# Intake — `iwm-vol-overlay-1d` research basis

**Family:** Volatility-managed **long-only overlay** on a **slow** time-series momentum base for **IWM** (US Russell 2000 ETF), daily bars — not crypto TSMOM, not pairs, not perp carry.

## Status — dropped

**Hypothesis id:** `iwm-vol-overlay-1d` · **Dropped** 2026-11-01 on branch `cursor/iwm-vol-overlay-1d-12eb` ([PR #26](https://github.com/mitchgad/week-trader/pull/26)).

Moreira & Muir ([DOI 10.1111/jofi.12513](https://doi.org/10.1111/jofi.12513)) weight is **σ*/realized vol**; the shared Alpaca **paper account caps execution at 1.0× the strategy slice** (5000 USD). After the signal was changed to that weight, Jev **`vol_overlay_long_only_honest`** fell from **0.61** to **0.59** (spec bar 0.65). That is the drop. **No paper-forward, no order.** Signed spec gate logs stay in `gates/iwm-vol-overlay-1d/`.

## C7 sketch → frozen spec (archived)

| Layer | Source | Role in spec |
|-------|--------|----------------|
| Vol-managed scaling | Moreira & Muir, *Journal of Finance* 2017, [DOI 10.1111/jofi.12513](https://doi.org/10.1111/jofi.12513) | **`w_t = σ*/σ_{t-1}`** (here `sigma_star / rv_21`); scale **up** when vol is low and **down** when vol is high — no artificial `min(1.0,·)` on the signal. |
| Slow directional base | Jegadeesh & Titman (1993); Moskowitz, Ooi & Pedersen (2012) TSMOM — C7 in [algorithms-and-paper-trade.md](../../docs/algorithms-and-paper-trade.md) §C7 | **12-1 month** daily momentum on IWM; flat when not `base_long` (no short). |
| Long-only + paper | Alpaca paper equities | **No short**; `w_t` may exceed 1 when σ is low (Moreira); **executed** size bounded by **5000 USD slice** and account **buying power** in `paper-order`. |

**Why IWM:** Liquid US small-cap ETF with daily Alpaca equity data; distinct symbol owner from BTC/ETH on the shared paper account.

**Why not parked:** Was implementable on Alpaca paper without short, paid data, or live endpoints — dropped instead after spec gate (see **Status — dropped**).

## Limits (not literature-settled)

- Moreira & Muir evidence is primarily **US equity factors** at **monthly** frequency; this spec uses **daily** bars with **21-day** realized vol and a **252/21** momentum base — **portability to IWM daily is unproven**.
- Crypto vol dynamics in C7 (original sketch) do **not** apply; this ID is **equity ETF only**.
- Passing paper forward does **not** validate economic edge — operational parity only.

## Alpaca paper

| Field | Value |
|-------|--------|
| Symbol | `IWM` |
| Bars | Daily (US regular session) |
| Orders | `paper-api.alpaca.markets` only |
| Proof | Forward events in `paper/iwm-vol-overlay-1d/forward/` |

## Rejected for this ID

BTC/ETH spot TSMOM; SPY or other equity symbols; short IWM; inverse/leveraged ETFs; perp funding proof; backtest-as-paper-proof.
