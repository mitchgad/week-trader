# Intake — `spy-equity-tsmom-1d` research basis

**Purpose:** Cited motivation for a **daily**, **long-only**, **SPY-only** time-series momentum portability spec on Alpaca paper. **Not a claim of net edge** at this bar size after costs.

**Scope:** US equity ETF (SPY); Alpaca paper equities rail only (`https://paper-api.alpaca.markets`). No paid data. FNArena off.

---

## What the literature supports (daily equity horizon)

| Claim | Source | Limitation for this spec |
|-------|--------|---------------------------|
| **Time-series momentum** (sign of own past return, often vol-scaled) persists across asset classes including **equity indices** at **1–12 month** horizons | Moskowitz, Ooi & Pedersen (2012), *Journal of Financial Economics*, [DOI 10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003) — verified Yes in project momentum map §B1 | Canonical formation is **months**, not a single tuned day count; **crash sensitivity** on equity index trend (Daniel & Moskowitz 2016, map §D1). |
| TSMOM on **spot and futures** with equity market coverage | Georgopoulou & Wang (2017), *Review of Finance*, [DOI 10.1093/rof/rfw048](https://doi.org/10.1093/rof/rfw048) — Partial DOI; manuscript mirrors in map §B6 | Post-crisis **regime / intervention** caveats in paper; not an Alpaca execution study. |
| Long-sample **trend** evidence and **cost** discussion | Hurst, Ooi & Pedersen (2017), AQR JPM PDF — map §B2, verified Yes | Managed-futures framing; SPY long-only is a **subset** of full trend programs. |
| **Trading costs** shrink anomaly portfolios when turnover rises | Frazzini, Israel & Moskowitz (2018), *RFS* lineage, [DOI 10.1093/rfs/hhv063](https://doi.org/10.1093/rfs/hhv063) — Partial in map §F1 | Daily rebalance on **one** liquid ETF is cheaper than multi-name CSMOM, but **gross ≠ net** still applies. |
| **Short lookback** trend weaker in long history | Lempérière et al. (2014), arXiv [1404.3274](https://arxiv.org/abs/1404.3274) — map §B5 | Warns against assuming **sub-month** trend strength; this spec uses **~6 month** daily formation as a **literature-anchored** compromise, not an optimized parameter. |

Project map [`research-momentum.md`](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-momentum.md) §B and §H: **TSMOM on equities at daily+** is **thick**; **true 1–5 day** alpha is **thin**. This hypothesis uses **1Day** bars with a **multi-month formation** — a **portability** design, not proof of edge.

---

## What this spec does **not** assume

- Cross-sectional winner/loser ranks (Jegadeesh–Titman CSMOM) as the signal.
- Perp funding, crypto carry, or Binance-style tail mechanics (see gap-fill for crypto; **out of scope** here).
- That backtest or engine parity satisfies Gate 3 — **paper forward only** per project gates.
- Live Alpaca (`api.alpaca.markets`) — **forbidden** in v1.

---

## Venue

- Alpaca **paper** supports US **equities** alongside crypto spot ([Alpaca paper trading docs](https://docs.alpaca.markets/docs/paper-trading)).
- Symbol **must** be **SPY** (project assignment); no symbol substitution.

---

## Honest synthesis for freeze

**Allowed:** Freeze a **falsifiable** daily long-only TSMOM rule on SPY with manifest costs and Alpaca paper forward as the only operational proof path.

**Not allowed:** Claim literature **proves** net profitability for this exact formation length on SPY after Alpaca fees/slippage; cite map §H when interpreting results.
