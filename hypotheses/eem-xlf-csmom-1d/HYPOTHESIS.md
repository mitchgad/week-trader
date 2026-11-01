# Hypothesis `eem-xlf-csmom-1d` (spec)

**Family:** Long-only **cross-sectional momentum** between **EEM** and **XLF**.

**Status:** Spec for human freeze. **No edge claimed.** See [docs/intake/eem-xlf-csmom-1d-research.md](../../docs/intake/eem-xlf-csmom-1d-research.md).

## Economic mechanism

Test whether **relative strength** between **EEM** and **XLF** over a **21-trading-day** formation predicts **continued outperformance** of the prior **winner** when implemented as **long-only** exposure (no short of the loser), after manifest costs on **Alpaca equity paper**.

Motivation (not proof): Jegadeesh & Titman (*Journal of Finance*, 1993, [DOI 10.1111/j.1540-6261.1993.tb04728.x](https://doi.org/10.1111/j.1540-6261.1993.tb04728.x)) document cross-sectional momentum in equities. This spec is a **two-name portability test**, not a broad stock cross-section.

## Long-only scope (Israel & Moskowitz)

Classic cross-sectional momentum **longs winners and shorts losers**. This hypothesis **never shorts** the relative loser: it holds **long only the symbol with the higher formation return** and switches when rank flips. Israel & Moskowitz (*Journal of Financial Economics*, 2013, [DOI 10.1016/j.jfineco.2012.11.005](https://doi.org/10.1016/j.jfineco.2012.11.005)) show **long-only** implementations retain much of the long–short spread **without** a short book. That supports a falsifiable **long-only winner-leg** test; it is **not** a claim that the full two-sided momentum portfolio is replicated.

## Universe and horizon

- **Universe:** `EEM` and `XLF` ETFs only (Alpaca US equity).
- **Bar interval:** 1Day (US regular session close, America/New_York calendar).
- **Hold:** Re-evaluate daily at cash close; target symbol may switch when relative rank flips.

## Signal and timing

- **Formation:** Simple return over the prior **21** completed daily closes per symbol: `close[t-1] / close[t-22] - 1`.
- **Signal at day *t* close:** **Long** the symbol with **higher** formation return; **no short** of the other (long-only constraint).
- **Order:** Next **regular-session** open after signal for the **target** symbol; no extended-hours fills.
- **Exit / switch:** When the other symbol becomes the relative winner at a subsequent daily close, rotate long exposure to the new winner (single long name at a time).

## Sizing and risk

- Long-only; notional capped by `config/paper_guards/eem-xlf-csmom-1d.json` and shared `risk_limits.json`.
- Shared Alpaca paper account; `paper/_shared/ACCOUNT_HALT` blocks all strategies.

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_equity |
| `paper_venue` | alpaca_paper |
| `instrument_class` | equity_etf |
| `allowed_symbols` | `EEM`, `XLF` |

## Costs

Manifest `data/manifests/eem-xlf-csmom-1d-alpaca.yaml` (`fee_bps_per_side`, `slippage_bps_per_side`; funding fields **null**).

## Validation and promotion proof

Operational proof is **Alpaca paper equity forward** only — not backtest replay as Gate 3 proof.

| Allowed proof | Forbidden as proof |
|---------------|-------------------|
| Forward events in `paper/eem-xlf-csmom-1d/forward/` | Short-loser leg or full long–short momentum without shorts |
| Daily `paper-forward` signals on manifest **EEM/XLF** | Crypto **perp** or **funding** P&L |

## Kill conditions (algorithms A.6 — pre-registered)

Archive if OOS / walk-forward paths fail preregistration hurdles, **2×** cost stress removes mean return, or implementation audit finds lookahead/session violations.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| Long-only winner **underperforms** equal-weight EEM+XLF after identical costs on OOS | Momentum structure adds nothing at this two-ETF horizon. |
| **2×** slippage stress removes OOS mean return | Cost-dominated. |
| Promotion cites **short loser** leg or **crypto/perp funding** evidence | Venue/spec violation — kill. |
| Rank uses symbols outside **EEM/XLF** | Universe violation — kill. |

**Out of scope:** Broad stock cross-section; SPY, IWM, GLD, BTC, ETH, DIA, TLT, IEF.
