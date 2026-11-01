# Hypothesis `xbi-max-short-1d` (frozen spec — paper forward)

**Replaces parked:** C4 **MAX lottery reversal** — **short XBI** when 21-day **MAX** (max daily return over window) is in top 80th percentile of 252-day history. **Not** sector CSMOM and **not** time-series momentum.

**Status:** Frozen. **No edge claimed.** **Portability test.**

Motivation (not proof): Bali, Cakici & Whitelaw (2011) MAX lottery premium [DOI 10.1111/j.1540-6261.2011.03.013.x](https://doi.org/10.1111/j.1540-6261.2011.03.013.x).

## Universe and horizon

- **Symbol:** **XBI** only (biotech ETF — lottery-like single-sector proxy on paper).
- **Bar interval:** 1Day.
- **Signal:** **Short** when MAX statistic is elevated; **flat** otherwise. Signal uses **extreme daily return lottery (MAX)** — not past 12-month return momentum.

## Signal and timing

- Daily US equity close; Alpaca paper short when enabled.

## Sizing and risk

- `config/paper_guards/xbi-max-short-1d.json` (**5000 USD** reference).

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_equities |
| `paper_venue` | alpaca_paper |
| `instrument_class` | equity |
| `allowed_symbols` | `XBI` |

## Validation and promotion proof

Alpaca paper forward with short leg.

## Costs

Manifest `data/manifests/xbi-max-short-1d-alpaca.yaml`.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| Promotion cites **live Alpaca host** or **crypto perp funding** proof | Venue violation — kill. |
| Gate 3 proof relies on **backtest only** without paper forward | Proof contract violation — kill. |
| Signal re-labeled as **TSMOM** or sector **CSMOM** | Mechanism mismatch — kill. |

**Out of scope:** owned symbols; paid data; XLP/XLK relative-winner rules.
