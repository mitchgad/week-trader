# Hypothesis `vb-vv-size-spread-1d` (frozen spec — paper forward)

**Replaces parked:** C5 **alt size** — **long VB / short VV** when small-cap trailing return exceeds large-cap (Fama-French size spread). **Not** long-only TSMOM.

**Status:** Frozen. **No edge claimed.** **Portability test.**

Motivation (not proof): Fama & French (1993) SMB size factor [DOI 10.1111/j.1540-6261.1993.tb04325.x](https://doi.org/10.1111/j.1540-6261.1993.tb04325.x).

## Universe and horizon

- **Symbols:** **VB** (small-cap), **VV** (large-cap core) only.
- **Bar interval:** 1Day.
- **Signal:** If 21-day return(VB) > return(VV) → **long VB**, **short VV**; else **flat both legs**.

## Signal and timing

- Daily closes; relative return spread at completed session close.

## Two-leg execution (Alpaca paper)

When the size spread is positive, this spec **requires both legs**: **buy VB** and **short VV**. Alpaca paper supports US equity shorts when enabled. **VV** is the large-cap leg — **not** SPY, IVV, VOO, DIA, QQQ, or IWM. If paper rejects **short VV** systematically, treat as **disconfirmer** — do not promote long-only VB proxy.

## Sizing and risk

- `config/paper_guards/vb-vv-size-spread-1d.json` (**$5000** reference).

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_equities |
| `paper_venue` | alpaca_paper |
| `instrument_class` | equity |
| `allowed_symbols` | `VB`, `VV` |

## Validation and promotion proof

Alpaca paper pairs forward — not backtest as Gate 3 proof.

## Costs

Manifest `data/manifests/vb-vv-size-spread-1d-alpaca.yaml`.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| Promotion cites **live Alpaca host** or **crypto perp funding** proof | Venue violation — kill. |
| Gate 3 proof relies on **backtest only** without paper forward | Proof contract violation — kill. |
| Promotion cites **crypto/perp funding** or **basis** carry | Venue violation — kill. |
| Promotion uses **long-only VB** without **short VV** | Spec violation — kill. |

**Out of scope:** owned symbols; paid data; single-name TSMOM.
