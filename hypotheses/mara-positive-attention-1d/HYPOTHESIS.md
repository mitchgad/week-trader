# Hypothesis `mara-positive-attention-1d` (frozen spec — paper forward)

**Replaces parked:** C1 **investor attention long BTC** — **MARA** equity + Google Trends **positive** attention ratio (`marathon digital` / `bitcoin stock`). **Not** BTC/USD and **not** TSMOM.

**Status:** Frozen for Alpaca **paper** forward. **No edge claimed.** Positive-attention predictability is documented for crypto; MARA keyword transfer is an **unproven portability test**.

Motivation (not proof): Liu & Tsyvinski (2021) investor attention [DOI 10.1093/rfs/hhaa113](https://doi.org/10.1093/rfs/hhaa113).

## Universe and horizon

- **Symbol:** **MARA** only.
- **Bar interval:** 1Day US session.
- **Signal:** **Long** when positive/baseline Trends ratio ≥ 80th percentile of prior **252** completed days; else **flat**.

## Signal and timing

- Free Google Trends US; drop partial days per manifest.
- **Positive attention ratio** — distinct from **GLD/SLV negative-attention** sleeves.

## Sizing and risk

- Long-only; `config/paper_guards/mara-positive-attention-1d.json` (**5000 USD** slice).

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_equities |
| `paper_venue` | alpaca_paper |
| `instrument_class` | equity |
| `allowed_symbols` | `MARA` |

## Validation and promotion proof

Alpaca paper forward + Trends events — not backtest as Gate 3 proof.

## Costs

Manifest `data/manifests/mara-positive-attention-1d-alpaca.yaml`.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| Promotion cites **live Alpaca host** or **crypto perp funding** proof | Venue violation — kill. |
| Gate 3 proof relies on **backtest only** without paper forward | Proof contract violation — kill. |
| Trends series **invented** or not fetchable on free Google Trends | Data contract violation — kill. |

**Out of scope:** BTC/ETH spot sleeves; GLD negative-attention keywords.
