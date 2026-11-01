# Parked strategies — Alpaca paper (v1)

**Purpose:** Record strategy families and example hypotheses **not** run on the project’s **Alpaca paper** account in v1. No `hypotheses/` specs, Jev questions, backtests, or orders for these IDs here.

**Active builds (do not duplicate):** `btc-spot-tsmom-4h` (BTC/USD), `eth-spot-tsmom-4h` (ETH/USD), `dia-mean-reversion-1d` (DIA), `eem-xlf-csmom-1d` (EEM, XLF), `tlt-ief-pairs-1d` (TLT, IEF). One owner per symbol.

**Alpaca paper equity shorts (2026-11-01):** Alpaca’s [Paper Trading](https://docs.alpaca.markets/us/docs/paper-trading) feature table lists **Short Selling ✅** on paper (same API as live, paper base URL only). Project paper account `shorting_enabled=true`. **Crypto spot cannot be shorted** on Alpaca — alt short sleeves stay parked.

**Sources:** [week-trader-plan.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/week-trader-plan.md), [research-gap-fill.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-gap-fill.md), [research-mean-reversion.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-mean-reversion.md), [research-premia-crypto.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-premia-crypto.md), [algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md).

---

## Carry / funding / basis / perps

**Status:** parked

Alpaca paper is **US equities + crypto spot sim only** — it does **not** model perp **funding**, **ADL**, **liquidation**, or **mark-price** tail mechanics ([week-trader-plan.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/week-trader-plan.md) §4.4–§4.5; [algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md) A.2 `venue_contract`). BIS crypto carry and He et al. (*Fundamentals of Perpetual Futures*, [arXiv:2212.06888](https://arxiv.org/abs/2212.06888)) are **perp–spot / funding** economics ([research-gap-fill.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-gap-fill.md) §1, §3). **Do not** fake a spot-only version of funding harvest or basis trades on Alpaca.

---

## C8 — volume-clock session momentum (BTC)

**Status:** parked

Example spec is **1-minute / session** horizon (3 weeks **1m** paper) ([algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md) C8; [week-trader-plan.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/week-trader-plan.md) §5.4). Week trader scope is **hours to several days**, not minute-scale session bots (plan horizon paragraph).

---

## C6 — cross-exchange Bitcoin discount slope

**Status:** parked

Requires **multi-leg** long/short across **two or more venues**; Makarov & Schoar (*JFE* 2020, [DOI 10.1016/j.jfineco.2019.07.001](https://doi.org/10.1016/j.jfineco.2019.07.001)) documents capital-control and transfer frictions ([algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md) C6, A.5). v1 paper rail is **Alpaca only** — not a second exchange leg.

---

## C1 — investor attention (Google Trends) long BTC

**Status:** parked

**BTC/USD** spot momentum / directional BTC work is owned by **`btc-spot-tsmom-4h`**. One owner per symbol; do not move BTC to attention or parallel BTC long specs ([week-trader-plan.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/week-trader-plan.md) §5.4 C1 sketch cites Liu & Tsyvinski, [DOI 10.1093/rfs/hhaa113](https://doi.org/10.1093/rfs/hhaa113)).

---

## Process / risk / execution / validation

**Status:** not-a-strategy

Sizing, vol targeting, costs, walk-forward, paper parity, and regime overlays are **disciplines**, not entry signals ([research-process-risk.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-process-risk.md); [algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md) Part A). Example **C7** (vol-managed overlay) is an overlay on a base rule, not a standalone Alpaca backlog item.

---

## Mean reversion (family)

**Status:** active build — **`dia-mean-reversion-1d`** (DIA daily long-only **loser leg**; Israel & Moskowitz long-only scope). Not parked for lack of equity shorts.

**Still parked (crypto):** BTC/alt spot MR — contested dynamics and **no crypto short** on Alpaca ([research-gap-fill.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-gap-fill.md) §2).

---

## Pairs / statistical arbitrage (family)

**Status:** active build — **`tlt-ief-pairs-1d`** (TLT/IEF daily spread convergence; Gatev-style distance pairs). ETB Treasury ETFs on Alpaca paper with **equity shorting enabled** — not parked for lack of a short leg.

**Still parked:** Crypto / perp **basis** pairs ([research-premia-crypto.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-premia-crypto.md) carry class) and multi-venue arb.

---

## Cross-sectional momentum (family)

**Status:** active build — **`eem-xlf-csmom-1d`** (long-only relative winner between **EEM** and **XLF** only; Israel & Moskowitz 2013 long-only momentum; Jegadeesh–Titman rank logic). Does **not** use SPY, IWM, GLD, BTC, ETH, DIA, TLT, or IEF.

---

## C3 — network adoption tilt

**Status:** parked

Published construction uses **on-chain / network** factors with vendor latency and revision risk ([algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md) C3; Liu & Tsyvinski [DOI 10.1093/rfs/hhaa113](https://doi.org/10.1093/rfs/hhaa113)). Honest replication needs **timestamped vendor data**, not free Alpaca OHLCV alone; multi-coin versions need **PIT listing** rules ([research-gap-fill.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-gap-fill.md) §5).

---

## C4 — cross-sectional MAX lottery reversal (alts)

**Status:** parked

Spec is **long lowest MAX quintile, short highest** among ~20 alts ([algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md) C4; Grobys & Junttila, [DOI 10.1016/j.intfin.2021.101289](https://doi.org/10.1016/j.intfin.2021.101289)). Requires **short** leg and a **point-in-time alt universe** — not available free on Alpaca paper.

---

## C5 — cross-sectional size (alts)

**Status:** parked

**Long small-cap / short large-cap** quintiles among liquid alts ([algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md) C5; Liu, Tsyvinski & Wu, [DOI 10.1111/jofi.13119](https://doi.org/10.1111/jofi.13119)). Needs **short**, **market-cap panel**, and **PIT delist** hygiene ([research-gap-fill.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-gap-fill.md) §5) — off v1 Alpaca-only, free-data rail.
