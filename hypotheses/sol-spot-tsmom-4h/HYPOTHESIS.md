# Hypothesis `sol-spot-tsmom-4h` (frozen spec — paper forward)

**Family:** 4h **SOL/USD spot** time-series momentum (long-only).

**Status:** Frozen. **No edge claimed.** Replaces C6 cross-exchange discount — **single-venue** Alpaca spot only.

Motivation (not proof): Tzouvanas et al. ([DOI 10.1016/j.econlet.2019.108728](https://doi.org/10.1016/j.econlet.2019.108728)).

## Universe and horizon

- **Symbol:** **SOL/USD** spot only.
- **Bar interval:** 4h UTC.
- **Signal:** Long if 6-bar formation log-return > 0; else flat.

## Signal and timing

- Next bar open orders; no perp funding.

## Sizing and risk

- Long-only; `config/paper_guards/sol-spot-tsmom-4h.json` slice **5000 USD**.

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_crypto |
| `paper_venue` | alpaca_paper |
| `instrument_class` | crypto_spot |
| `allowed_symbols` | `SOL/USD` |

## Validation and promotion proof

Alpaca paper crypto spot forward — not cross-venue arb proof.

## Costs

Manifest `data/manifests/sol-spot-tsmom-4h-alpaca.yaml`; funding null.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| Promotion cites second-venue discount or transfer arb | Wrong venue class — kill. |
| Promotion cites **perp funding** PnL as spot proof | Venue violation — kill. |
| Gate 3 proof relies on **backtest only** | Proof contract violation — kill. |
