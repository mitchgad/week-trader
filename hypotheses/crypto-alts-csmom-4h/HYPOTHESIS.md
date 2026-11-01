# Hypothesis `crypto-alts-csmom-4h` (frozen spec — paper forward)

**Replaces parked:** C6 **cross-exchange discount** — **long-only cross-sectional momentum** among Alpaca **crypto spot** alts (SOL, LTC, AVAX). **Single venue**; **not** single-name time-series momentum and **not** two-exchange arb.

**Status:** Frozen. **No edge claimed.** **Portability test.**

Motivation (not proof): Tzouvanas et al. (2019) cross-sectional crypto momentum [DOI 10.1016/j.econlet.2019.108728](https://doi.org/10.1016/j.econlet.2019.108728).

## Universe and horizon

- **Symbols:** **SOL/USD**, **LTC/USD**, **AVAX/USD** (manifest list).
- **Bar interval:** 4h UTC.
- **Signal:** At each bar close, rank **cross-sectional** 6-bar formation log-returns; **long** the relative winner only. **Not** independent TSMOM on one coin.

## Signal and timing

- Cross-section rank at bar close; Alpaca crypto spot only (no short).
- Long-only **cross-sectional momentum (CSMOM)** — falsifiable separately from BTC/ETH spot TSMOM sleeves.

## Sizing and risk

- `config/paper_guards/crypto-alts-csmom-4h.json` (**5000 USD** slice on winner leg).

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_crypto |
| `paper_venue` | alpaca_paper |
| `instrument_class` | crypto_spot |
| `allowed_symbols` | `SOL/USD`, `LTC/USD`, `AVAX/USD` |

## Validation and promotion proof

Alpaca paper crypto spot forward.

## Costs

Manifest `data/manifests/crypto-alts-csmom-4h-alpaca.yaml`.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| Promotion cites **live Alpaca host** or **crypto perp funding** proof | Venue violation — kill. |
| Gate 3 proof relies on **backtest only** without paper forward | Proof contract violation — kill. |
| Winner leg chosen by **single-asset TSMOM** only (ignoring cross-section) | Spec violation — kill. |

**Out of scope:** BTC/ETH owned sleeves; paid multi-venue discount data.
