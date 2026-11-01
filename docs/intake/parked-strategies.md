# Parked strategies — Alpaca paper (v1)

**Purpose:** Record strategy families **not** run on Alpaca paper in v1. Active replacements below are **forward-testable** on the shared paper account (see `hypotheses/`).

**Active builds (do not duplicate):** `btc-spot-tsmom-4h`, `eth-spot-tsmom-4h`, `spy-equity-tsmom-1d`, `dia-mean-reversion-1d`, `eem-xlf-csmom-1d`, `tlt-ief-pairs-1d`, `gld-negative-attention-1d`, plus replacements: `usmv-equity-tsmom-1d`, `qqq-equity-tsmom-1d`, `vb-equity-tsmom-1d`, `sol-spot-tsmom-4h`, `slv-negative-attention-1d`, `mstr-equity-tsmom-1d`, `xlp-xlk-csmom-1d`. One owner per symbol.

**Alpaca paper equity shorts (2026-11-01):** [Paper Trading](https://docs.alpaca.markets/docs/paper-trading) lists **Short Selling ✅**. Crypto spot cannot be shorted.

**Sources:** Project store docs (`week-trader-plan.md`, `research-gap-fill.md`, `algorithms-and-paper-trade.md`).

---

## Carry / funding / basis / perps → **`usmv-equity-tsmom-1d`**

**Status:** **active** — daily long-only **USMV** time-series momentum on Alpaca paper equities. **Not** crypto funding, basis, or perp carry ([research-gap-fill.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-gap-fill.md) §1). Moskowitz, Ooi & Pedersen (2012) TSMOM [DOI 10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003).

---

## C8 — volume-clock session momentum (BTC) → **`qqq-equity-tsmom-1d`**

**Status:** **active** — **daily QQQ** TSMOM (hours–days horizon), **not** 1-minute BTC session bars ([algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md) C8 scope).

---

## C6 — cross-exchange Bitcoin discount slope → **`sol-spot-tsmom-4h`**

**Status:** **active** — **single-venue SOL/USD** spot 4h TSMOM on Alpaca paper. **Not** two-venue discount slope (Makarov & Schoar [DOI 10.1016/j.jfineco.2019.07.001](https://doi.org/10.1016/j.jfineco.2019.07.001) requires multi-venue legs).

---

## C1 — investor attention long BTC → **`mstr-equity-tsmom-1d`**

**Status:** **active** — **MSTR** equity daily TSMOM (crypto-adjacent single name). **Not** BTC/USD (owned by `btc-spot-tsmom-4h`) and **not** Google Trends attention. Moskowitz, Ooi & Pedersen TSMOM [DOI 10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003). *(Dropped after spec gate fail: `coin-positive-attention-1d` — Trends/attention spec gate.)*

---

## Process / risk / execution / validation

**Status:** not-a-strategy — discipline map only ([research-process-risk.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-process-risk.md)).

---

## Mean reversion (family)

**Status:** active — **`dia-mean-reversion-1d`**. Crypto spot MR still parked (no crypto short).

---

## Pairs / statistical arbitrage (family)

**Status:** active — **`tlt-ief-pairs-1d`**. Crypto/perp basis pairs still parked.

---

## Cross-sectional momentum (family)

**Status:** active — **`eem-xlf-csmom-1d`**.

---

## C3 — network adoption tilt → **`slv-negative-attention-1d`**

**Status:** **active** — **SLV** negative-attention ratio via **free Google Trends**, **not** paid on-chain network factors (Liu & Tsyvinski network metrics require vendor on-chain data [DOI 10.1093/rfs/hhaa113](https://doi.org/10.1093/rfs/hhaa113)).

---

## C4 — cross-sectional MAX lottery reversal (alts) → **`xlp-xlk-csmom-1d`**

**Status:** **active** — long-only **XLP vs XLK** relative winner (Israel & Moskowitz 2013 long-only CSMOM [DOI 10.1016/j.jfineco.2012.11.005](https://doi.org/10.1016/j.jfineco.2012.11.005)). **Not** alt MAX short quintiles. *(Dropped after spec gate fail: `xbi-max-reversal-short-1d` — single-name MAX short spec gate.)*

---

## C5 — cross-sectional size (alts) → **`vb-equity-tsmom-1d`**

**Status:** **active** — **long-only VB** small-cap ETF daily TSMOM. **Not** long-small/short-large alt quintiles (Liu, Tsyvinski & Wu alt size [DOI 10.1111/jofi.13119](https://doi.org/10.1111/jofi.13119) needs PIT cap panel + shorts).
