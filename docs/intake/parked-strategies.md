# Parked strategies — Alpaca paper (v1)

**Purpose:** Record strategy families **not** run on Alpaca paper in v1. Active replacements below are **forward-testable** on the shared paper account (see `hypotheses/`).

**Active builds (do not duplicate):** `btc-spot-tsmom-4h`, `eth-spot-tsmom-4h`, `spy-equity-tsmom-1d`, `dia-mean-reversion-1d`, `eem-xlf-csmom-1d`, `tlt-ief-pairs-1d`, `gld-negative-attention-1d`, plus replacements: `vgit-shy-term-carry-1d`, `qqq-volume-confirm-1d`, `vb-vv-size-spread-1d`, `crypto-alts-csmom-4h`, `slv-negative-attention-1d`, `mara-positive-attention-1d`, `xbi-max-short-1d`. One owner per symbol.

**Alpaca paper equity shorts (2026-11-01):** [Paper Trading](https://docs.alpaca.markets/docs/paper-trading) lists **Short Selling ✅**. Crypto spot cannot be shorted.

**Sources:** Project store docs (`week-trader-plan.md`, `research-gap-fill.md`, `algorithms-and-paper-trade.md`).

---

## Carry / funding / basis / perps → **`vgit-shy-term-carry-1d`**

**Status:** **active** — **VGIT/SHY** Treasury term-structure carry pair on Alpaca paper (long VGIT / short SHY when carry proxy is rich). **Not** crypto funding, basis, or perp carry ([research-gap-fill.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-gap-fill.md) §1). Fama & Bliss (1987) [DOI 10.3386/w1963](https://doi.org/10.3386/w1963).

---

## C8 — volume-clock session momentum (BTC) → **`qqq-volume-confirm-1d`**

**Status:** **active** — **daily QQQ** volume–return confirmation (Campbell, Grossman & Wang 1993 [DOI 10.1086/296921](https://doi.org/10.1086/296921)), **not** 1-minute BTC session bars ([algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md) C8 scope).

---

## C6 — cross-exchange Bitcoin discount slope → **`crypto-alts-csmom-4h`**

**Status:** **active** — **long-only cross-sectional momentum** on Alpaca crypto spot alts (SOL, LTC, AVAX). **Single venue**; **not** two-venue discount slope (Makarov & Schoar [DOI 10.1016/j.jfineco.2019.07.001](https://doi.org/10.1016/j.jfineco.2019.07.001) requires multi-venue legs). Tzouvanas et al. (2019) [DOI 10.1016/j.econlet.2019.108728](https://doi.org/10.1016/j.econlet.2019.108728).

---

## C1 — investor attention long BTC → **`mara-positive-attention-1d`**

**Status:** **active** — **MARA** equity + **positive** Google Trends attention (`marathon digital` / `bitcoin stock`). **Not** BTC/USD (owned by `btc-spot-tsmom-4h`) and **not** TSMOM. Liu & Tsyvinski (2021) [DOI 10.1093/rfs/hhaa113](https://doi.org/10.1093/rfs/hhaa113).

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

**Status:** **active** — **SLV** negative-attention ratio via **free Google Trends**, **not** paid on-chain network factors (Liu & Tsyvinski [DOI 10.1093/rfs/hhaa113](https://doi.org/10.1093/rfs/hhaa113)).

---

## C4 — cross-sectional MAX lottery reversal (alts) → **`xbi-max-short-1d`**

**Status:** **active** — **short XBI** when 21-day **MAX** is historically elevated. Bali, Cakici & Whitelaw (2011) [DOI 10.1111/j.1540-6261.2011.03.013.x](https://doi.org/10.1111/j.1540-6261.2011.03.013.x). **Not** sector CSMOM.

---

## C5 — cross-sectional size (alts) → **`vb-vv-size-spread-1d`**

**Status:** **active** — **long VB / short VV** size spread on Alpaca paper. Fama & French (1993) [DOI 10.1111/j.1540-6261.1993.tb04325.x](https://doi.org/10.1111/j.1540-6261.1993.tb04325.x). **Not** long-only small-cap TSMOM; **VV** is the large-cap leg (not SPY/IVV/VOO/DIA/QQQ/IWM).
