# Intake — `eth-spot-tsmom-4h` research basis

**Family:** Time-series / short-horizon **momentum** on **ETH/USD crypto spot** (not mean reversion, not carry/funding, not equity pairs).

## Why ETH and this family

| Source | Claim used in spec | Limit |
|--------|-------------------|-------|
| Tzouvanas, Kizys & Tsend-Ayush, *Economics Letters* 2020, [DOI 10.1016/j.econlet.2019.108728](https://doi.org/10.1016/j.econlet.2019.108728) | Cross-sectional momentum among **twelve** cryptocurrencies is significant at **short** horizons and **fades** at longer horizons (abstract). Supports testing **alt** momentum, not BTC-only carry. | Daily panel; **no** net fees/funding; does not name ETH alone. |
| Liu & Tsyvinski, NBER WP 24877, [https://www.nber.org/papers/w24877](https://www.nber.org/papers/w24877) | **Time-series momentum** among crypto factor predictors on **daily** CoinDesk BTC (and broader crypto factor set). | Daily bar evidence; **portability to 4h ETH spot is unproven** ([research-gap-fill.md](../../docs/research-gap-fill.md) §1). |
| Week trader gap fill §1 | Gross crypto momentum ≠ net 4h–5d edge after costs; true hours–days canon is **thin**. | Mandatory cost manifest + kill rules; no literature-settled ETH 4h claim. |

**Rejected for this ID:** BTC mean reversion (gap-fill §2 contested); equity pairs/stat-arb (not a Bitcoin/ETH spot TSMOM story); funding/basis/perp sleeves on Alpaca paper.

## Alpaca paper

ETH/USD is available as **crypto spot** on Alpaca paper alongside BTC/USD. Perp funding and ADL are **out of scope** (same venue contract pattern as `btc-spot-tsmom-4h`).
