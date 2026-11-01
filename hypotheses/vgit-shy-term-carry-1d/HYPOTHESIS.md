# Hypothesis `vgit-shy-term-carry-1d` (frozen spec — paper forward)

**Replaces parked:** crypto **carry/funding/perps** — **US Treasury ETF term-structure carry** on Alpaca paper (long VGIT / short SHY when curve carry proxy is rich). **Not** TSMOM and **not** crypto funding.

**Status:** Frozen. **No edge claimed.** **Portability test.**

Motivation (not proof): Fama & Bliss (1987) bond return predictability [DOI 10.3386/w1963](https://doi.org/10.3386/w1963); Ilmanen (2011) carry premia taxonomy.

## Universe and horizon

- **Symbols:** **VGIT**, **SHY** only.
- **Bar interval:** 1Day.
- **Signal:** When log(VGIT/SHY) z-score ≥ +1 vs 63-day history → **long VGIT**, **short SHY**; else flat both legs.

## Signal and timing

- Spread z from rolling log price ratio (duration carry proxy).
- Formation window ends at *t−1*; signal at completed daily close *t*.

## Two-leg execution (Alpaca paper)

When carry is rich, this spec **requires both legs**: **buy VGIT** and **short SHY** on the same signal day. Alpaca paper supports US equity short selling when `shorting_enabled` is true. **SHY** and **VGIT** are treated as easy-to-borrow Treasury ETFs on paper. If paper rejects systematic **short SHY** fills, treat as **disconfirmer** — do not promote on long-only VGIT proxy.

## Sizing and risk

- Pair notional via `config/paper_guards/vgit-shy-term-carry-1d.json` (**$5000** reference per guard).

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_equities |
| `paper_venue` | alpaca_paper |
| `instrument_class` | equity |
| `allowed_symbols` | `VGIT`, `SHY` |

## Validation and promotion proof

Alpaca paper **two-leg** forward only — not backtest replay as Gate 3 proof.

## Costs

Manifest `data/manifests/vgit-shy-term-carry-1d-alpaca.yaml`.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| Promotion cites **live Alpaca host** or **crypto perp funding** proof | Venue violation — kill. |
| Gate 3 proof relies on **backtest only** without paper forward | Proof contract violation — kill. |
| Promotion uses **long-only VGIT** without **short SHY** leg | Spec violation — kill. |

**Out of scope:** owned symbols; paid data; Moskowitz TSMOM on single names.
