# Hypothesis `spy-equity-tsmom-1d` (frozen spec — not traded until gates)

**Family:** Time-series momentum on **SPY** US equity ETF (Moskowitz, Ooi & Pedersen TSMOM lineage; **not** cross-sectional CSMOM, not crypto, not carry/funding).

**Status:** Frozen spec for Jev and paper forward. **No edge claimed.** Daily equity TSMOM is **literature-supported at multi-month horizons**; **net profitability on this exact rule after Alpaca costs is unproven** ([docs/intake/spy-equity-tsmom-1d-research.md](../../docs/intake/spy-equity-tsmom-1d-research.md)).

## Economic mechanism

Test whether **past SPY daily returns** over a fixed formation window predict **same-direction** long-only exposure over subsequent **days to weeks**, after manifest slippage and fee assumptions on **Alpaca paper equities**.

Motivation (not proof): Moskowitz, Ooi & Pedersen (2012, [DOI 10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003)) document **time-series momentum** across futures and related markets at **1–12 month** horizons; Georgopoulou & Wang (2017, [DOI 10.1093/rof/rfw048](https://doi.org/10.1093/rof/rfw048)) study TSMOM on **equity** markets. This spec **ports** the sign-of-past-return idea to **daily SPY bars** with a **126-session formation** (~six months) — a **portability test**, not a production signal.

## Universe and horizon

- **Universe:** **SPY** only (single symbol; assignment-fixed).
- **Bar interval:** 1Day (US equity session calendar via manifest timezone).
- **Hold:** Enter after signal at next session open; hold up to **63** completed daily bars (~three months) or until signal flat, whichever first.

## Signal and timing

- **Formation:** Sum of log returns over the prior **126** completed daily sessions (~six months).
- **Signal at session *t* close:** `long` if formation return > 0; `flat` otherwise (long-only — no short).
- **Order:** Next session open after signal; no intrabar fills.
- **Exit:** Flat when formation return ≤ 0 at daily close, or max hold reached.

## Sizing and risk

- Long-only; notional capped by `config/paper_guards/spy-equity-tsmom-1d.json` strategy slice (**5000 USD**) and `risk_limits.json`.
- Shared Alpaca paper account; **BTC/USD and ETH/USD remain owned by their hypotheses**.

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_equities |
| `paper_venue` | alpaca_paper |
| `instrument_class` | equity |
| `allowed_symbols` | `SPY` only |
| `paper_api_host` | `https://paper-api.alpaca.markets` only |

Alpaca paper simulates **US equities** on the paper host — **never** the live trading host. **Gate 4 live trading is blocked** in v1.

## Validation and promotion proof

Operational proof is **Alpaca paper equity forward** tracking only — not backtest replay as Gate 3 proof.

| Allowed proof | Forbidden as proof |
|---------------|-------------------|
| Alpaca paper **equity** forward in `paper/spy-equity-tsmom-1d/forward/` | **Live** Alpaca host orders or fills |
| `paper-forward` daily signals on manifest `SPY` | Crypto perp funding, carry, or BTC/ETH forward logs as SPY proof |
| Signed Jev **trade** gate + `paper-order` when signal and intent match | Backtest-only promotion without paper forward |

## Costs

Manifest `data/manifests/spy-equity-tsmom-1d-alpaca.yaml` — `fee_bps_per_side`, `slippage_bps_per_side`; **`funding_series_id` must stay null** (equities rail).

## Kill conditions (algorithms A.6)

Archive if on concatenated OOS / walk-forward paths:

1. Haircut-adjusted OOS Sharpe or profit factor **below** preregistered hurdle given trial count **N**.
2. Net return **≤ 0** after manifest costs on OOS with **≥ 20** round-trips, **or** result **vanishes** under **2×** cost stress (Frazzini et al. cost skepticism).
3. **Horizon fade:** OOS performance **concentrated** in one subperiod **or** sign **flips** across adjacent folds without pre-specified regime switch.
4. **Implementation audit** finds lookahead, session timing mismatch, or fill rule violation.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| OOS long-only TSMOM **underperforms** SPY buy-and-hold after identical costs | No gross structure at this horizon for this rule. |
| **2×** fee + slippage stress removes positive OOS mean return | Cost-dominated — kill. |
| Signal **inverts** on OOS folds | Contradicts TSMOM direction — not mean-reversion rescue. |
| Promotion cites **live Alpaca host** (`api.alpaca.markets`) or non-paper credentials | **Venue violation** — falsifies frozen contract; kill immediately. |
| Gate 3 proof relies on **backtest metrics only** without paper forward | Proof contract violation — kill. |

**Out of scope:** Crypto spot/perp sleeves; cross-sectional equity momentum ranks; minute scalping.
