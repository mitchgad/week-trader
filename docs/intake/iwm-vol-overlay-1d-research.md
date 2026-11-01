# Intake — `iwm-vol-overlay-1d` research basis

**Family:** Volatility-managed **long-only overlay** on a **slow** time-series momentum base for **IWM** (US Russell 2000 ETF), daily bars — not crypto TSMOM, not pairs, not perp carry.

## C7 sketch → frozen spec

| Layer | Source | Role in spec |
|-------|--------|----------------|
| Vol-managed scaling | Moreira & Muir, *Journal of Finance* 2017, [DOI 10.1111/jofi.12513](https://doi.org/10.1111/jofi.12513) | Scale exposure inversely with **prior** realized volatility; improves risk-adjusted returns on factor portfolios in their sample. |
| Slow directional base | Jegadeesh & Titman (1993) monthly momentum; Moskowitz, Ooi & Pedersen (2012) time-series momentum — cited in Moreira & Muir; Week trader C7 example in [algorithms-and-paper-trade.md](../../docs/algorithms-and-paper-trade.md) §C7 | **12-1 month** style daily momentum on IWM: long when 12-month return minus most recent month is positive; **flat** otherwise (no short leg). |
| Long-only honesty | Project constraint + Alpaca paper | Overlay weight capped at **1.0** (no leverage beyond full notional); weight **0** when base flat. No short selling, no vol-target leverage above 100% long exposure. |

**Why IWM:** Liquid US small-cap ETF with daily Alpaca equity data; distinct symbol owner from BTC/ETH on the shared paper account.

**Why not parked:** Design is implementable **long-only** on Alpaca paper with free Alpaca market data — no paid vendor, no short, no margin beyond cash long within the **5000 USD** strategy slice.

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
