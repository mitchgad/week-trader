# Shared Alpaca paper account guards

v1 runs multiple hypotheses on **one** Alpaca paper account. `paper-order` enforces guards from `paper_account_guards.json` **after** hypothesis `HALT` and **before** any `https://paper-api.alpaca.markets` call.

## Order of checks

1. Signed trade gate, hypothesis `HALT`, `risk_limits.json`
2. **Account halt** — `paper/_shared/ACCOUNT_HALT` (blocks every strategy)
3. Symbol owner, capital slice, opposite open-order lock
4. Alpaca submit with strategy **fill tag** as `client_order_id` prefix

## Config (`paper_account_guards.json`)

| Field | Role |
|-------|------|
| `account_halt_file` | Shared kill switch above strategy slices |
| `symbol_owners` | One hypothesis id per normalized symbol (`BTCUSD`, `BTC/USD`, …) |
| `strategy_slices` | Per-hypothesis `max_notional_usd` and `fill_tag` |

Fill submissions append to `paper/_shared/fill_tags.jsonl` (repo-local attribution; Alpaca does not tag positions).

## Capital slice notional

Projected notional = existing position market value on the symbol + open orders tagged with this strategy’s fill tag + new order (`qty × reference price`). Reference price comes from intent `reference_price_usd` or the latest forward `signal` event `last_close`.

## Dry run

Create `paper/_shared/ACCOUNT_HALT` and run `paper-order` with a valid trade gate — must fail with **zero** broker HTTP calls.
