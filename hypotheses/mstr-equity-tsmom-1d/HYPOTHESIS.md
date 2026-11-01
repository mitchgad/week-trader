# Hypothesis `mstr-equity-tsmom-1d` (frozen spec — paper forward)

**Replaces parked:** C1 investor attention long **BTC** — **MSTR** equity daily TSMOM (crypto-adjacent single name, **not** BTC/USD and **not** Google Trends).

**Status:** Frozen. **No edge claimed.** **Portability test.**

Motivation (not proof): Moskowitz, Ooi & Pedersen ([DOI 10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003)).

## Universe and horizon

- **Symbol:** **MSTR** only.
- **Bar interval:** 1Day.
- **Signal:** Long-only 126-day formation TSMOM; flat if formation return ≤ 0.

## Signal and timing

- Daily US session close signal; next open orders.

## Sizing and risk

- `config/paper_guards/mstr-equity-tsmom-1d.json` (**5000 USD** slice).

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_equities |
| `paper_venue` | alpaca_paper |
| `instrument_class` | equity |
| `allowed_symbols` | `MSTR` |

## Validation and promotion proof

Alpaca paper equity forward only.

## Costs

Manifest `data/manifests/mstr-equity-tsmom-1d-alpaca.yaml`.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| Promotion uses **BTC/USD** forward logs as MSTR proof | Symbol violation — kill. |
| Promotion cites **live Alpaca host** or perp funding | Venue violation — kill. |
| Gate 3 proof relies on **backtest only** | Proof contract violation — kill. |
