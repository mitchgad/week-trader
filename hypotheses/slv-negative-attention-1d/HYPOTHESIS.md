# Hypothesis `slv-negative-attention-1d` (frozen spec — paper forward)

**Family:** Negative attention ratio on **SLV** (daily, long-only).

**Status:** Frozen for Alpaca **paper** forward. **No edge claimed.** Replaces C3 on-chain adoption tilt.

## Economic mechanism

Port **negative attention ratio** (`silver crash` / `silver price`, US Google Trends) to **SLV** — **not** paid on-chain network adoption metrics.

Motivation (not proof): Liu & Tsyvinski ([DOI 10.1093/rfs/hhaa113](https://doi.org/10.1093/rfs/hhaa113)).

## Universe and horizon

- **Symbol:** **SLV** only.
- **Bar interval:** 1Day US session.
- **Signal:** Flat if ratio ≥ 80th percentile of prior 252 completed Trends days; else long.

## Signal and timing

- Free Google Trends; drop partial days per manifest.

## Sizing and risk

- Long-only; `config/paper_guards/slv-negative-attention-1d.json` (**5000 USD** slice).

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_equities |
| `paper_venue` | alpaca_paper |
| `instrument_class` | equity |
| `allowed_symbols` | `SLV` |

## Validation and promotion proof

Alpaca paper forward only — not backtest as Gate 3 proof.

## Costs

Manifest `data/manifests/slv-negative-attention-1d-alpaca.yaml`.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| Promotion cites on-chain adoption data as proof | Wrong feature class — kill. |
| Promotion cites **live Alpaca host** or perp funding | Venue violation — kill. |
| Gate 3 proof relies on **backtest only** | Proof contract violation — kill. |

**Out of scope:** owned symbols; paid data; cross-exchange legs.
