from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist, mean, pstdev
from typing import Any

# Frozen forward-paper fleet size for deflated-Sharpe selection bias (README 2026-11-02).
ACTIVE_FORWARD_HYPOTHESIS_IDS: tuple[str, ...] = (
    "btc-spot-tsmom-4h",
    "eth-spot-tsmom-4h",
    "crypto-alts-csmom-4h",
    "spy-equity-tsmom-1d",
    "dia-mean-reversion-1d",
    "eem-xlf-csmom-1d",
    "tlt-ief-pairs-1d",
    "vgit-shy-term-carry-1d",
    "vb-vv-size-spread-1d",
    "gld-negative-attention-1d",
    "slv-negative-attention-1d",
    "mara-positive-attention-1d",
    "qqq-volume-confirm-1d",
    "xbi-max-short-1d",
)

RUNNING_STRATEGY_COUNT = len(ACTIVE_FORWARD_HYPOTHESIS_IDS)
PSR_CONFIDENCE = 0.95
MIN_EXPOSURE_USD = 50.0
MIN_RETURN_OBSERVATIONS = 5

_NORM = NormalDist()


@dataclass(frozen=True)
class SharpeInference:
    sharpe_ratio: float
    skewness: float
    kurtosis: float
    observation_count: int
    benchmark_sharpe: float
    probabilistic_sharpe_ratio: float
    min_track_record_length: float
    deflated_sharpe_threshold: float


def build_strategy_attribution(
    hypothesis_id: str,
    positions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Mark-to-market on manifest symbols only (shared account; not whole-account equity)."""
    from week_trader.paper_forward import manifest_universe_symbols

    manifest_syms = {_normalize_symbol(s) for s in manifest_universe_symbols(hypothesis_id)}
    gross_market_value_usd = 0.0
    unrealized_pl_usd = 0.0
    held: list[dict[str, Any]] = []
    for position in positions:
        raw_symbol = position.get("symbol")
        if not isinstance(raw_symbol, str):
            continue
        sym = _normalize_symbol(raw_symbol)
        if sym not in manifest_syms:
            continue
        qty = _float_or_zero(position.get("qty"))
        if qty == 0.0:
            continue
        market_value = _float_or_zero(position.get("market_value"))
        unrealized = _float_or_zero(position.get("unrealized_pl"))
        gross_market_value_usd += abs(market_value)
        unrealized_pl_usd += unrealized
        held.append(
            {
                "symbol": raw_symbol,
                "qty": qty,
                "market_value": market_value,
                "unrealized_pl": unrealized,
            }
        )
    return {
        "manifest_symbols": sorted(manifest_syms),
        "gross_market_value_usd": round(gross_market_value_usd, 6),
        "unrealized_pl_usd": round(unrealized_pl_usd, 6),
        "positions": held,
    }


def build_forward_evidence_check(
    hypothesis_id: str,
    *,
    forward_directory: Path,
) -> dict[str, Any]:
    """
    Probabilistic Sharpe, MinTRL, and deflated benchmark for forward paper only.
    Does not affect Jev gates or declare promotion — surfaces evidence readiness.
    """
    events_path = forward_directory / "events.jsonl"
    snapshots = _load_attributed_snapshots(events_path)
    returns, return_meta = _strategy_returns_from_snapshots(snapshots, hypothesis_id)
    inference = _sharpe_inference(returns, running_strategies=RUNNING_STRATEGY_COUNT)
    evidence_status, status_detail = _evidence_status(inference, return_meta)

    report: dict[str, Any] = {
        "hypothesis_id": hypothesis_id,
        "timestamp_utc": _utc_now(),
        "validation_mode": "forward_paper_only",
        "running_strategy_count": RUNNING_STRATEGY_COUNT,
        "evidence_status": evidence_status,
        "evidence_status_detail": status_detail,
        "return_basis": "manifest_symbol_mark_to_market_snapshots",
        "returns": return_meta,
        "inference": _inference_dict(inference) if inference else None,
        "not_enough_data_yet": evidence_status == "insufficient_data",
    }
    forward_directory.mkdir(parents=True, exist_ok=True)
    (forward_directory / "evidence.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def probabilistic_sharpe_ratio(
    sharpe_ratio: float,
    benchmark_sharpe: float,
    *,
    observation_count: int,
    skewness: float,
    kurtosis: float,
) -> float:
    """PSR = Prob(true SR > benchmark | sample SR, T, skew, kurtosis). Bailey / López de Prado."""
    if observation_count < 2:
        return 0.0
    denom = _sharpe_variance_denominator(sharpe_ratio, skewness, kurtosis)
    if denom <= 0:
        return 0.0
    z = (sharpe_ratio - benchmark_sharpe) * math.sqrt(observation_count - 1) / math.sqrt(denom)
    return _NORM.cdf(z)


def min_track_record_length(
    sharpe_ratio: float,
    benchmark_sharpe: float,
    *,
    skewness: float,
    kurtosis: float,
    confidence: float = PSR_CONFIDENCE,
) -> float:
    """Minimum T such that PSR >= confidence at the observed Sharpe (MinTRL)."""
    if sharpe_ratio <= benchmark_sharpe:
        return math.inf
    denom = _sharpe_variance_denominator(sharpe_ratio, skewness, kurtosis)
    if denom <= 0:
        return math.inf
    z_alpha = _NORM.inv_cdf(confidence)
    z_delta = (sharpe_ratio - benchmark_sharpe) / math.sqrt(denom)
    if z_delta <= 0:
        return math.inf
    return 1.0 + (z_alpha / z_delta) ** 2


def deflated_sharpe_threshold(
    *,
    running_strategies: int,
    observation_count: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """
    Expected maximum Sharpe under null from N concurrent forward strategies (selection bias).
    Bailey & López de Prado deflated Sharpe benchmark (SR0).
    """
    if running_strategies < 2 or observation_count < 2:
        return 0.0
    euler = 0.5772156649015329
    z1 = _NORM.inv_cdf(1.0 - 1.0 / running_strategies)
    z2 = _NORM.inv_cdf(1.0 - 1.0 / (running_strategies * math.e))
    max_z = (1.0 - euler) * z1 + euler * z2
    sr_variance = _sharpe_variance_denominator(0.0, skewness, kurtosis) / max(observation_count - 1, 1)
    return max_z * math.sqrt(sr_variance)


def _sharpe_inference(returns: list[float], *, running_strategies: int) -> SharpeInference | None:
    if len(returns) < 2:
        return None
    obs = len(returns)
    mu = mean(returns)
    sigma = pstdev(returns)
    if sigma <= 0:
        return None
    sharpe = mu / sigma
    skew = _skewness(returns)
    kurt = _kurtosis(returns)
    benchmark = deflated_sharpe_threshold(
        running_strategies=running_strategies,
        observation_count=obs,
        skewness=skew,
        kurtosis=kurt,
    )
    psr = probabilistic_sharpe_ratio(
        sharpe,
        benchmark,
        observation_count=obs,
        skewness=skew,
        kurtosis=kurt,
    )
    min_trl = min_track_record_length(
        sharpe,
        benchmark,
        skewness=skew,
        kurtosis=kurt,
        confidence=PSR_CONFIDENCE,
    )
    return SharpeInference(
        sharpe_ratio=sharpe,
        skewness=skew,
        kurtosis=kurt,
        observation_count=obs,
        benchmark_sharpe=benchmark,
        probabilistic_sharpe_ratio=psr,
        min_track_record_length=min_trl,
        deflated_sharpe_threshold=benchmark,
    )


def _evidence_status(
    inference: SharpeInference | None,
    return_meta: dict[str, Any],
) -> tuple[str, str]:
    obs = int(return_meta.get("observation_count", 0))
    if obs < MIN_RETURN_OBSERVATIONS:
        return "insufficient_data", "fewer than minimum return observations for Sharpe inference"
    if inference is None:
        return "insufficient_data", "not enough data yet to estimate Sharpe"
    psr = inference.probabilistic_sharpe_ratio
    if psr <= 1.0 - PSR_CONFIDENCE:
        return "fail", "PSR below tail vs deflated benchmark"
    min_trl = inference.min_track_record_length
    if not math.isfinite(min_trl) or obs < min_trl:
        return (
            "insufficient_data",
            "track record shorter than MinTRL for a deflated Sharpe verdict",
        )
    if psr >= PSR_CONFIDENCE:
        return "pass", "PSR meets confidence vs deflated benchmark (not promotion proof)"
    return "inconclusive", "PSR between pass and fail tails"


def _strategy_returns_from_snapshots(
    snapshots: list[dict[str, Any]],
    hypothesis_id: str,
) -> tuple[list[float], dict[str, Any]]:
    slice_notional = _strategy_slice_notional(hypothesis_id)
    returns: list[float] = []
    skipped_no_exposure = 0
    prior_mark: float | None = None
    for row in snapshots:
        mark = _float_or_zero(row.get("gross_market_value_usd"))
        if mark < MIN_EXPOSURE_USD:
            prior_mark = mark if mark > 0 else prior_mark
            skipped_no_exposure += 1
            continue
        if prior_mark is None or prior_mark < MIN_EXPOSURE_USD:
            prior_mark = mark
            continue
        pl_delta = mark - prior_mark
        if slice_notional > 0:
            returns.append(pl_delta / slice_notional)
        else:
            returns.append(pl_delta / prior_mark)
        prior_mark = mark
    return returns, {
        "observation_count": len(returns),
        "snapshot_count": len(snapshots),
        "skipped_no_exposure_snapshots": skipped_no_exposure,
        "slice_notional_usd": slice_notional,
    }


def _load_attributed_snapshots(events_path: Path) -> list[dict[str, Any]]:
    if not events_path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event_type") != "pnl_snapshot":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        attr = payload.get("strategy_attribution")
        if isinstance(attr, dict):
            rows.append(
                {
                    "timestamp_utc": event.get("timestamp_utc"),
                    "gross_market_value_usd": attr.get("gross_market_value_usd"),
                }
            )
    return rows


def _strategy_slice_notional(hypothesis_id: str) -> float:
    try:
        from week_trader.paper_account_guards import load_guards_config, strategy_slice

        guards = load_guards_config()
        entry = strategy_slice(guards, hypothesis_id)
        return float(entry["max_notional_usd"])
    except (KeyError, TypeError, ValueError, OSError):
        return 5000.0


def _inference_dict(inference: SharpeInference) -> dict[str, Any]:
    min_trl = inference.min_track_record_length
    return {
        "sharpe_ratio": round(inference.sharpe_ratio, 8),
        "skewness": round(inference.skewness, 8),
        "kurtosis": round(inference.kurtosis, 8),
        "observation_count": inference.observation_count,
        "deflated_sharpe_threshold": round(inference.deflated_sharpe_threshold, 8),
        "benchmark_sharpe": round(inference.benchmark_sharpe, 8),
        "probabilistic_sharpe_ratio": round(inference.probabilistic_sharpe_ratio, 8),
        "min_track_record_length": min_trl if math.isfinite(min_trl) else None,
        "psr_confidence": PSR_CONFIDENCE,
    }


def _sharpe_variance_denominator(sharpe_ratio: float, skewness: float, kurtosis: float) -> float:
    return 1.0 - skewness * sharpe_ratio + ((kurtosis - 1.0) / 4.0) * sharpe_ratio**2


def _skewness(values: list[float]) -> float:
    if len(values) < 3:
        return 0.0
    mu = mean(values)
    m2 = sum((x - mu) ** 2 for x in values) / len(values)
    if m2 <= 0:
        return 0.0
    m3 = sum((x - mu) ** 3 for x in values) / len(values)
    return m3 / (m2**1.5)


def _kurtosis(values: list[float]) -> float:
    if len(values) < 4:
        return 3.0
    mu = mean(values)
    m2 = sum((x - mu) ** 2 for x in values) / len(values)
    if m2 <= 0:
        return 3.0
    m4 = sum((x - mu) ** 4 for x in values) / len(values)
    return m4 / (m2**2)


def _normalize_symbol(symbol: str) -> str:
    cleaned = symbol.strip().upper()
    if "/" in cleaned:
        return cleaned.replace("/", "")
    return cleaned


def _float_or_zero(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
