# Hypothesis `usmv-equity-tsmom-1d` (frozen spec — paper forward)

**Family:** Daily TSMOM on USMV

**Status:** Frozen for Alpaca **paper** forward. **No edge claimed.** Portability test only.

## Economic mechanism

Test **time-series momentum** on **USMV** (min-vol US equity ETF) as a **paper-testable US equity** rule — **not** crypto funding, basis, or perp carry (BIS / He et al. perp economics do not apply on Alpaca spot).

## Universe and horizon

- **Symbol:** **USMV** only.
- **Bar interval:** 1Day (US session).
- **Signal:** Long-only TSMOM — **126**-session formation log-return sum; flat if ≤ 0.
- **Order:** Next session open after signal.

## Sizing and risk

- Long-only; `config/paper_guards/usmv-equity-tsmom-1d.json` slice **5000 USD** max notional.

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_equities |
| `paper_venue` | alpaca_paper |
| `instrument_class` | equity |
| `allowed_symbols` | `USMV` |

## Validation and promotion proof

Operational proof is **Alpaca paper equity forward** only — not backtest as Gate 3 proof.

## Costs

Manifest `data/manifests/usmv-equity-tsmom-1d-alpaca.yaml`.


## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| OOS / forward underperforms buy-and-hold after manifest costs | No gross structure for this rule. |
| Promotion cites **live Alpaca host** or perp funding proof | Venue violation — kill. |
| Gate 3 proof relies on **backtest only** without paper forward | Proof contract violation — kill. |

**Out of scope:** BTC/ETH/SPY/GLD/DIA/EEM/XLF/TLT/IEF/IWM symbols; paid data; cross-exchange legs.


**Replaces parked:** Carry / funding / basis / perps — this is **daily US equity TSMOM**, not crypto funding/carry/perps.
