# Intake — cross-sectional momentum (parked)

**Suggested id:** `equity-cs-momentum-1d` (not built).

**Status:** Parked. No Jev, no orders.

## Assignment constraint

Do not use SPY, IWM, GLD, BTC, ETH, DIA, TLT, or IEF. A cross-sectional momentum sleeve outside that set requires either:

1. A **broad point-in-time equity universe** with liquidity filters (not free CRSP-grade hygiene on Alpaca alone), or  
2. **Short losers** (Jegadeesh & Titman 1993 winner–loser spread [10.1111/j.1540-6261.1993.tb04702.x](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x)).

Long-only top-decile momentum without a defined multi-name universe is not the cited CSMOM design ([research-momentum.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-momentum.md) §A1, Israel & Moskowitz 2013 on long-only capture).

## Why parked

Honest implementation needs **shorts and/or a PIT cross-section** we cannot assert from free Alpaca bars alone ([algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md) A.3; [research-gap-fill.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-gap-fill.md) §5).

## Resume when

Frozen PIT universe manifest + shortability model, or a human-narrowed long-only ETF basket with explicit Israel & Moskowitz long-only citation and accepted scope creep.
