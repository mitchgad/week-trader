# Hypothesis `gld-negative-attention-1d` (frozen spec — paper forward)

**Family:** C2 **negative attention ratio** on **GLD** (daily bars, long-only).

**Status:** Frozen for Alpaca **paper** forward. **No edge claimed.** Negative-attention predictability is documented primarily for **Bitcoin**; GLD keyword transfer is an **unproven portability test**, not production alpha.

## Economic mechanism

Test whether a **high ratio of negative to baseline Google search interest** (`gold crash` / `gold price`, US) predicts **lower risk-adjusted exposure** to **GLD** at a **daily** rebalance horizon — implemented as **flat in the top historical quintile** of the ratio and **long otherwise** (long-only constraint on Alpaca paper).

Motivation (not proof): Liu & Tsyvinski link **negative attention ratios** to subsequent returns at **~1 week** horizons in crypto ([RFS 2021](https://doi.org/10.1093/rfs/hhaa113); [NBER WP 24877](https://www.nber.org/papers/w24877)). Project C2 sketch ([algorithms-and-paper-trade.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/algorithms-and-paper-trade.md) §C2) uses Google search ratios; this spec **ports the structure** to **GLD** with **free** Trends data only.

## Universe and horizon

- **Symbol:** **GLD** only (SPDR Gold Shares ETF).
- **Bar interval:** 1d (US session calendar in manifest).
- **Signal:** At each **completed** Trends day *t*, compare ratio to the **80th percentile** of the prior **252** completed daily ratios; **flat** if ratio ≥ threshold, else **long**.
- **Order:** Next session open after signal (paper-order intent); no intraday fills in v1 forward logger.

## Signal and timing

- **Attention:** Google Trends US relative interest for **`gold crash`** (numerator) and **`gold price`** (denominator, min 1).
- **Drop partial days:** Trends `isPartial` rows excluded before quintile math.
- **Price observation:** Latest Alpaca **GLD daily close** logged with signal for notional reference only.

## Sizing and risk

- Long-only; strategy capital slice **`max_notional_usd` 5000** via `config/paper_guards/gld-negative-attention-1d.json` (merged at order time).
- Account halt `paper/_shared/ACCOUNT_HALT` and hypothesis `paper/gld-negative-attention-1d/HALT` block all activity.

## Venue contract

| Field | Value |
|-------|--------|
| `execution_venue` | alpaca_equities |
| `paper_venue` | alpaca_paper |
| `instrument_class` | equity |
| `allowed_symbols` | `GLD` |

Alpaca paper simulates **US equities** only for this ID — no crypto spot/perp, no live endpoints.

## Validation and promotion proof

Operational proof is **Alpaca paper forward** tracking (`paper/gld-negative-attention-1d/forward/`) — **not** backtest replay for v1 promotion.

| Allowed proof | Forbidden as proof for this ID |
|---------------|--------------------------------|
| Forward `signal` events with live Trends + GLD close metadata | Hand-written or synthetic attention CSVs |
| Alpaca paper **GLD** fills via `paper-order` | Crypto BTC/ETH forward logs as GLD proof |
| Signed Jev **trade** gate matching intent | Backtest-only metrics without forward bars |

Intake: [docs/intake/gld-negative-attention-1d-research.md](../../docs/intake/gld-negative-attention-1d-research.md).

## Costs

Manifest `data/manifests/gld-negative-attention-1d-alpaca.yaml` — zero explicit commission bps (Alpaca paper default) + **5 bps/side** slippage stress line for documentation; forward P&amp;L is **paper sim**, not a cost study.

## Kill conditions (plan C2 sketch — paper phase)

Archive paper experiment if, over pre-registered forward window:

1. **≥ 8** high-ratio signal days and high-ratio **forward weeks** do **not** show worse GLD paper sim returns than low-ratio weeks (Welch *p* > 0.10) — per [week-trader-plan.md](/cursor/stores/bc-01a1908d-055d-7ab4-b664-480c480c321a/docs/week-trader-plan.md) C2 table.
2. Trends fetch **unavailable** for **5 consecutive** scheduled signal days (fail closed — no invented series).
3. Any order without matching **long** signal + fresh trade gate.

## Disconfirmers

| Disconfirmer | Interpretation |
|--------------|----------------|
| High-ratio days **do not** associate with worse subsequent GLD paper returns vs low-ratio days at registered threshold | Negative-attention structure **not supported** on GLD with these keywords. |
| Signal **inverts** (high ratio predicts **better** GLD returns) with pre-registered significance | Contradicts C2 directional story — kill. |
| Promotion cites **crypto perp funding**, **BTC/ETH** forward logs, or **backtest-only** metrics | Venue/proof violation — kill immediately. |
| Attention series **cannot** be fetched from free Google Trends in production loop | Operational falsification — park or halt (no synthetic fill). |

**Out of scope:** FNArena or paid sentiment; short GLD; intraday scalping; changing BTC/ETH/SPY/IWM hypotheses.
