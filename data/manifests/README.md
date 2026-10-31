# Data manifests

YAML manifests under this directory define **point-in-time** universe rules, bar conventions (UTC), vendor checksums, and **cost model fields**.

`make verify-backtest ID=<hypothesis>` and `make data-validate` refuse to run if:

- `costs.fee_bps_per_side`, `costs.slippage_bps_per_side` are missing
- Perp specs omit `costs.funding_interval_hours` and `costs.funding_series_id` when `instrument_class: crypto_perp`
- PIT rules are absent

Before promotion, run **engine parity** (primary vs Jesse golden slice): `make engine-parity ID=<hypothesis>` — see [docs/backtest-engines.md](../backtest-engines.md).

See `example-btc-spot.yaml` for shape. Licensed raw dumps do not belong in git.
