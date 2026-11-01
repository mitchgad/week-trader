# Intake — `tlt-ief-pairs-1d` (parked)

**Status:** Parked for v1 Alpaca paper. No Jev gate, no orders, no hypothesis directory.

## Family

Pairs / statistical arbitrage on **TLT** and **IEF** (Treasury duration spread).

## Why parked

Gatev–Goetzmann–Rouwenhorst-style and cointegration pairs ([DOI 10.1093/rfs/hhj020](https://doi.org/10.1093/rfs/hhj020); Vidyamurthy *Pairs Trading*, 2004) are **two-leg relative-value** books: long one ETF and **short** the other (or beta-hedged dollar-neutral). Week trader v1 paper is **long-only spot/equity** on a shared Alpaca account; rewriting a pairs spread into a single-leg proxy would not implement the cited design ([research-mean-reversion.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-mean-reversion.md) §4, P21–P23).

## Data

Free daily bars for TLT and IEF exist on Alpaca; the blocker is **short leg + spread neutrality**, not data cost.

## Resume when

Human approves short equity on paper (or a second venue with explicit borrow model) and a frozen two-leg manifest.

## Citations

- Gatev, Goetzmann & Rouwenhorst (2006), *RFS* [10.1093/rfs/hhj020](https://doi.org/10.1093/rfs/hhj020)
- Chan (2013), interday pairs rationale — Wiley [10.1002/9781118676998](https://onlinelibrary.wiley.com/doi/book/10.1002/9781118676998)
- Project map: [research-mean-reversion.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-mean-reversion.md) §4
