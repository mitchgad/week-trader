# Hypothesis `_template` (do not trade)

Copy to `hypotheses/<id>/` and replace placeholders. Freeze before backtest or any Jev call.

## Economic mechanism

_(Describe falsifiable story; link primary literature in intake — not chat lore.)_

## Universe and horizon

- **Universe:** _(e.g. BTC-USD spot on Alpaca)_
- **Bar interval:** _(e.g. 1h UTC)_
- **Hold:** hours to several days

## Signal and timing

- Signal known at bar *t* close; orders default *t+1* open unless pre-registered otherwise.

## Sizing and risk

- Max notional per `risk_limits.json` and preregistration caps.

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | |
| `paper_venue` | alpaca_paper (equities + crypto spot sim only) |
| `instrument_class` | equity \| crypto_spot \| crypto_perp |

**Perp specs:** document liquidation buffer, mark-vs-last, ADL/cross-margin in this file or **cannot paper**.

## Costs

Declared in bound data manifest (`costs.*`). Backtest must not run without fee, slippage, and funding (if perp) fields.

## Kill conditions

See algorithms doc A.6 — pre-register in `preregistration.json`.

## Disconfirmers

_(What result would falsify the mechanism?)_
