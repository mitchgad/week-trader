# Hypothesis `qqq-volume-confirm-1d` (frozen spec — paper forward)

**Replaces parked:** C8 **volume-clock session** — **daily QQQ volume–return confirmation** (Campbell, Grossman & Wang 1993). **Not** 1-minute session bars and **not** time-series momentum (Moskowitz-style past-return sign rules).

**Status:** Frozen. **No edge claimed.** **Portability test.**

Motivation (not proof): Campbell, Grossman & Wang (1993) trading volume and stock returns [DOI 10.1086/296921](https://doi.org/10.1086/296921).

## Universe and horizon

- **Symbol:** **QQQ** only.
- **Bar interval:** 1Day.
- **Signal:** **Long** when session return > 0 **and** share volume ≥ 1.5× trailing 20-day average; else **flat**. No signal from past multi-month return sign alone.

## Signal and timing

- Uses Alpaca daily **share volume** and split-adjusted closes.
- Volume confirmation rule is **not** TSMOM: it conditions on **same-day return sign** plus **relative volume**, not cumulative past winner/loser momentum.

## Sizing and risk

- `config/paper_guards/qqq-volume-confirm-1d.json` (**5000 USD** slice).

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_equities |
| `paper_venue` | alpaca_paper |
| `instrument_class` | equity |
| `allowed_symbols` | `QQQ` |

## Validation and promotion proof

Alpaca paper forward only.

## Costs

Manifest `data/manifests/qqq-volume-confirm-1d-alpaca.yaml`.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| Promotion cites **live Alpaca host** or **crypto perp funding** proof | Venue violation — kill. |
| Gate 3 proof relies on **backtest only** without paper forward | Proof contract violation — kill. |
| Signal re-labeled as **TSMOM** on QQQ | Mechanism mismatch — kill. |

**Out of scope:** owned symbols; paid data; minute scalping mislabeled as C8.
