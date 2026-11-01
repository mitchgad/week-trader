# btc-spot-tsmom-4h — venue proof contract (citations)

**Purpose:** Research-backed rules for what may count as operational proof for this **BTC spot** TSMOM spec on **Alpaca paper**. Feeds `HYPOTHESIS.md` and `preregistration.json` `proof_contract` — not a separate strategy.

## Why perp funding cannot prove this hypothesis

| Source | Relevance |
|--------|-----------|
| [research-gap-fill.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/research-gap-fill.md) §1 | **Carry / funding** and **spot TSMOM** are different economic objects; BIS WP 1087 and He et al. (arXiv:2212.06888) study **perp–spot / funding**, not long-only spot momentum after Alpaca spot fees. |
| [algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md) A.2, Part B §B.1 | Paper must match **`venue_contract` instrument class**; Alpaca paper is **equities + crypto spot sim only** — not BTC perp funding accrual. |
| [grokbot-army.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/grokbot-army.md) §4.1 | Perp hypotheses **must not** use Alpaca as paper venue; inverse: this spot hypothesis **must not** use perp/testnet P&amp;L as proof. |
| [week-trader-plan.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/week-trader-plan.md) §6 / promotion gates | Gate 3 paper rail must match spec; **Alpaca paper for perp-only proof is a block** — symmetrically, **perp funding proof is invalid for Alpaca spot specs**. |
| Alpaca [Paper Trading](https://docs.alpaca.markets/docs/paper-trading) | Paper sim for crypto **spot**; no documented perp funding schedule on this rail. |

## Allowed operational proof (this ID)

- Alpaca **paper** crypto **spot** orders and fills logged under `paper/btc-spot-tsmom-4h/forward/` and `paper/btc-spot-tsmom-4h/journal/`.
- Live 4h bar signal records from `paper-forward` using manifest symbol `BTC/USD` only.

## Forbidden as promotion or venue proof

- Any **perp funding** P&amp;L series, Binance Futures testnet/mock trading, or basis/carry backtests presented as validation of **this** spot TSMOM rule.
- Changing `instrument_class` to `crypto_perp` while keeping Alpaca `paper_venue` (manifest validator rejects this combination in code).
