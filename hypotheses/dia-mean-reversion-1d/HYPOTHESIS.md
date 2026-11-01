# Hypothesis `dia-mean-reversion-1d` (spec — not traded until gates)

**Family:** Short-horizon **contrarian mean reversion** on **DIA** (long-only loser leg).

**Status:** Draft spec for human freeze. **No edge claimed.** See [docs/intake/dia-mean-reversion-1d-research.md](../../docs/intake/dia-mean-reversion-1d-research.md).

## Economic mechanism

Test whether **prior-week losses** on DIA predict **positive** next-period returns when implemented as **long-only** exposure (contrarian **loser leg** only), after manifest costs on **Alpaca equity paper**.

Motivation (not proof): Lehmann (NBER WP 2533) documents **weekly reversal** after sorting on prior-week returns; Jegadeesh (1990) finds **negative short-horizon autocorrelation** at monthly horizons. This spec adapts the **loser-only** contrarian leg to **5 trading-day** formation on **daily** DIA bars — a **portability test**, not production alpha.

## Long-only scope (Israel & Moskowitz)

The published contrarian spread **longs prior losers and shorts prior winners** (Lehmann). This hypothesis **never shorts** DIA: it holds **long only when the formation return is negative** and is **flat otherwise**, omitting the short-winner leg. Israel & Moskowitz (*Journal of Financial Economics*, 2013, [DOI 10.1016/j.jfineco.2012.11.005](https://doi.org/10.1016/j.jfineco.2012.11.005)) show that **long-only** implementations of price anomalies retain a large fraction of the classic long–short spread **without** a short book. That supports a **falsifiable long-only loser-leg test**; it is **not** a claim that the full two-sided contrarian portfolio is replicated.

## Universe and horizon

- **Universe:** `DIA` ETF only.
- **Bar interval:** 1Day (US regular session close, America/New_York calendar).
- **Hold:** Enter after signal at next session open; hold up to **5 trading days** or until signal flat.

## Signal and timing

- **Formation:** Simple return over the prior **5** completed daily closes: `close[t-1] / close[t-6] - 1`.
- **Signal at day *t* close:** `long` if formation return **< 0**; `flat` otherwise (no short — long-only constraint).
- **Order:** Next **regular-session** open after signal; no extended-hours fills.
- **Exit:** Flat when formation return ≥ 0 at subsequent daily close, or max hold reached.

## Sizing and risk

- Long-only; notional capped by `config/paper_guards/dia-mean-reversion-1d.json` and `risk_limits.json`.
- Shared Alpaca paper account; account halt in `paper/_shared/ACCOUNT_HALT` blocks all strategies.

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_equity |
| `paper_venue` | alpaca_paper |
| `instrument_class` | equity_etf |
| `allowed_symbols` | `DIA` |

Alpaca paper does **not** model hard-to-borrow short locate for a full contrarian spread.

## Validation and promotion proof

Operational proof is **Alpaca paper equity forward** only — not backtest replay as Gate 3 proof.

| Allowed proof | Forbidden as proof |
|---------------|-------------------|
| Forward events in `paper/dia-mean-reversion-1d/forward/` | Full Lehmann long–short spread without short implementation |
| Daily `paper-forward` signals on manifest `DIA` | Crypto/perp venues |

## Costs

Manifest `data/manifests/dia-mean-reversion-1d-alpaca.yaml` (`fee_bps_per_side`, `slippage_bps_per_side`; funding fields **null**).

## Kill conditions (algorithms A.6 — pre-registered)

Archive if OOS / walk-forward paths fail preregistration hurdles, **2×** cost stress removes mean return, or implementation audit finds lookahead/session violations.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| Long-only loser leg **underperforms** buy-and-hold DIA after identical costs | Contrarian loser leg adds no structure at this horizon. |
| **2×** slippage stress removes OOS mean return | Cost-dominated. |
| Formation **positive** predicts **higher** next-week return (sign inversion) on OOS folds | Contradicts contrarian direction — kill. |
| Promotion cites **short winner leg** or **crypto/perp** results | Venue/spec violation — kill. |

**Out of scope:** Pairs (TLT/IEF), cross-sectional multi-name reversal requiring shorts, minute bars.
