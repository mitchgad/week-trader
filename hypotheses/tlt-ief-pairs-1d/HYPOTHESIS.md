# Hypothesis `tlt-ief-pairs-1d` (spec)

**Family:** **Pairs / statistical arbitrage** on **TLT** and **IEF** (Treasury duration spread).

**Status:** Spec for human freeze. **No edge claimed.** See [docs/intake/tlt-ief-pairs-1d-research.md](../../docs/intake/tlt-ief-pairs-1d-research.md).

## Economic mechanism

Test whether **mean reversion** in the **log price ratio** between **TLT** (long duration) and **IEF** (intermediate duration) predicts **convergence** when the spread is **far from its rolling mean**, implemented as a **two-leg** long/short on **Alpaca paper US equities** (easy-to-borrow Treasury ETFs), after manifest costs.

Motivation (not proof): Gatev, Goetzmann & Rouwenhorst (*Review of Financial Studies*, 2006, [DOI 10.1093/rfs/hhj020](https://doi.org/10.1093/rfs/hhj020)) document **distance** pairs trading on co-moving assets. TLT/IEF share duration exposure but differ in target maturity — a **relative-value** pair, not a crypto **basis** trade.

## Universe and horizon

- **Universe:** `TLT` and `IEF` only (Alpaca US equity ETFs; ETB names on paper).
- **Bar interval:** 1Day (US regular session close).
- **Hold:** While **|spread z-score| > exit band** after entry; flat when **|z| < 0.5**.

## Signal and timing

- **Spread:** \( s_t = \log(\text{TLT}_t) - \log(\text{IEF}_t) \) on each completed daily close.
- **Rolling stats:** Mean and sample std of \( s \) over the prior **60** sessions (ending at *t−1* for signal at *t* close — no same-bar lookahead in formation window).
- **Z-score:** \( z_t = (s_t - \mu_{60}) / \sigma_{60} \) (if \( \sigma_{60} > 0 \)).
- **Entry:** If \( z_t > +2 \): **long IEF**, **short TLT** (rich TLT vs IEF → convergence). If \( z_t < -2 \): **long TLT**, **short IEF**.
- **Exit:** If \( |z_t| < 0.5 \): **flat both legs** (no pair exposure).
- **Between bands** (\( 0.5 \le |z_t| \le 2 \) without fresh entry): hold prior pair state or remain flat per forward implementation — falsifiable via forward audit.

## Two-leg execution (Alpaca paper)

This spec **requires both legs** when `side=pairs`: one **buy** and one **sell/short** on the same signal day. Alpaca paper supports **US equity short selling** when account `shorting_enabled` is true (verified on project paper account). **TLT** and **IEF** are treated as **easy-to-borrow** Treasury ETFs on paper; hard-to-borrow locate is **not** fully simulated. If paper rejects systematic short fills, treat as **disconfirmer** — do not promote on long-only proxy.

## Sizing and risk

- Pair notional capped by `config/paper_guards/tlt-ief-pairs-1d.json` per leg (max **$5000** notional reference per guard file) and shared halt file.
- Gross exposure includes **long + short** notionals; account halt in `paper/_shared/ACCOUNT_HALT` blocks all strategies.

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_equity |
| `paper_venue` | alpaca_paper |
| `instrument_class` | equity_etf |
| `allowed_symbols` | `TLT`, `IEF` |

## Costs

Manifest `data/manifests/tlt-ief-pairs-1d-alpaca.yaml` (`fee_bps_per_side`, `slippage_bps_per_side`; funding **null**).

## Validation and promotion proof

Operational proof is **Alpaca paper equity forward** (two-leg intents and fills where shorts succeed) — not backtest replay as Gate 3 proof.

| Allowed proof | Forbidden as proof |
|---------------|-------------------|
| Forward events in `paper/tlt-ief-pairs-1d/forward/` with **long_symbol** + **short_symbol** | **Long-only single-leg** proxy of the pair |
| Alpaca paper equity order fills on **TLT** and **IEF** | Crypto **perp**, **carry**, or **basis** pairs |

## Kill conditions (algorithms A.6 — pre-registered)

Archive if OOS fails preregistration, **2×** cost stress removes mean return, spread **does not mean-revert** on OOS folds, or shorts systematically fail on paper.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| Paper **`shorting_enabled` false** or short orders **systematically rejected** | Cannot implement spec — kill. |
| Spread divergence persists (sign of z predicts **further** divergence OOS) | Pairs economics fail at this horizon — kill. |
| Promotion cites **crypto/perp funding** or **basis** carry | Venue violation — kill. |
| Promotion uses **long-only** proxy without short leg | Spec violation — kill. |

**Out of scope:** Crypto pairs; perp **basis**; multi-venue arb.
