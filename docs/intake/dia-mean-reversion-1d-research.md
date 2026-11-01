# Research — `dia-mean-reversion-1d`

**Family:** Short-horizon **contrarian / mean reversion** on a single US equity ETF (DIA).

## Primary citations (opened via DOI/NBER metadata)

| Source | Role for this spec |
|--------|-------------------|
| Lehmann (1990), NBER WP 2533 [https://www.nber.org/papers/w2533](https://www.nber.org/papers/w2533) | **Weekly** winner/loser portfolios show **reversal** next week; contrarian on prior-week losers. |
| Jegadeesh (1990), *JF* [10.1111/j.1540-6261.1990.tb05110.x](https://doi.org/10.1111/j.1540-6261.1990.tb05110.x) | **Negative short-horizon autocorrelation** at monthly frequency for stocks — motivates days-scale reversal tests. |
| Nagel (2012), NBER WP 17653 [https://www.nber.org/papers/w17653](https://www.nber.org/papers/w17653) | Reversal compensates **liquidity provision** — edge **regime-conditional** (VIX); spec must not treat reversal as free Sharpe. |
| Project map [research-mean-reversion.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-mean-reversion.md) §2 P5–P11 | Failure modes: lead-lag, liquidity, shorts required for full spread. |

## Portability (honest)

Literature contrarian portfolios **short winners**. This hypothesis is a **long-only loser leg** on **DIA** (Dow ETF) with **daily** bars and **5-day** formation — a **portability test**, not the full Lehmann spread. **No edge claimed.**

## Data

- **Free:** Alpaca IEX daily bars for `DIA` on paper account (US regular session).
- **Costs:** Manifest half-spread + commission bps; no borrow (long-only).

## Disallowed as proof

- Short-leg P&amp;L from academic winner–loser tables without implementation.
- Crypto or perp venues.
