# Hypothesis `qqq-equity-tsmom-1d` (frozen spec — paper forward)

**Family:** Daily TSMOM on QQQ

**Status:** Frozen for Alpaca **paper** forward. **No edge claimed.** Portability test only.

## Economic mechanism

Replace **1-minute BTC session** momentum with **daily QQQ** TSMOM at **hours–days** project horizon — same sign-of-past-return family, **not** volume-clock intraday bars.

## Universe and horizon

- **Symbol:** **QQQ** only.
- **Bar interval:** 1Day (US session).
- **Signal:** Long-only TSMOM — **126**-session formation log-return sum; flat if ≤ 0.
- **Order:** Next session open after signal.

## Sizing and risk

- Long-only; `config/paper_guards/qqq-equity-tsmom-1d.json` slice **5000 USD** max notional.

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_equities |
| `paper_venue` | alpaca_paper |
| `instrument_class` | equity |
| `allowed_symbols` | `QQQ` |

## Validation and promotion proof

Operational proof is **Alpaca paper equity forward** only — not backtest as Gate 3 proof.

## Costs

Manifest `data/manifests/qqq-equity-tsmom-1d-alpaca.yaml`.


## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| OOS / forward underperforms buy-and-hold after manifest costs | No gross structure for this rule. |
| Promotion cites **live Alpaca host** or perp funding proof | Venue violation — kill. |
| Gate 3 proof relies on **backtest only** without paper forward | Proof contract violation — kill. |

**Out of scope:** BTC/ETH/SPY/GLD/DIA/EEM/XLF/TLT/IEF/IWM symbols; paid data; cross-exchange legs.


**Replaces parked:** C8 volume-clock session momentum (BTC 1m) — this is **daily US equity TSMOM**, not crypto funding/carry/perps.
