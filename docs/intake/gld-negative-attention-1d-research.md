# Intake — `gld-negative-attention-1d` research basis

**Family:** C2 **negative attention ratio** on **GLD** (US listed gold ETF), adapted from Liu–Tsyvinski crypto attention evidence — **not** a mandate to copy the sample Bitcoin hack fail test verbatim.

## Why GLD and this family

| Source | Claim used in spec | Limit |
|--------|-------------------|-------|
| Project [algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md) §C2 | Weekly **ratio of negative to baseline Google search** predicts **1-week-ahead** returns in the original Bitcoin sample; high-ratio weeks treated as stress. | Keywords were “Bitcoin hack” / “Bitcoin”; **GLD uses** `gold crash` / `gold price` as free proxies — **unvalidated transfer**. |
| Liu & Tsyvinski, *Review of Financial Studies* (2021), [DOI 10.1093/rfs/hhaa113](https://doi.org/10.1093/rfs/hhaa113); NBER [WP 24877](https://www.nber.org/papers/w24877) | Investor **attention** and **negative attention ratio** as return predictors at **weekly** horizons in crypto. | Crypto venue; **not** GLD; post-publication and revision risk ([research-gap-fill.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-gap-fill.md) PIT notes for Trends). |
| [week-trader-plan.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/week-trader-plan.md) C2 kill sketch | Paper kill: high-ratio weeks should show **worse** forward sim returns vs low-ratio (Welch, ≥8 events). | **Paper-forward v1** records signals; formal kill stats deferred to forward journal. |

**Rejected for this ID:** Paid sentiment (FNArena, etc.); invented attention series; crypto perp funding proof; backtest-only promotion.

## Free attention data

- **Vendor:** Google Trends relative search interest (US), keywords **`gold crash`** (negative) and **`gold price`** (baseline), bound in `data/manifests/gld-negative-attention-1d-alpaca.yaml`.
- **Fetch check (2026-11-01):** Cloud agent retrieved **262** daily buckets via Google Trends in this run before rate-limit cooldown — series is **not** fabricated in-repo.
- **PIT:** Exclude `isPartial` days; expect Google revision of recent buckets ([algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md) A.3).

## Alpaca paper

**GLD** trades as a **US equity** on Alpaca paper (`paper-api.alpaca.markets`). Long-only; daily signal; orders only via `paper-order` + signed trade gate when signal is **long** and intent matches.
