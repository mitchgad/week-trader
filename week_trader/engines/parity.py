from __future__ import annotations

import json
from pathlib import Path

from week_trader.engines.golden_slice import primary_buy_hold_net_return
from week_trader.engines.jesse_adapter import JesseAdapterError, jesse_golden_slice_net_return
from week_trader.manifest import load_data_manifest, resolve_manifest_for_hypothesis
from week_trader.prereg import load_preregistration
from week_trader.util import hypothesis_dir, repo_root


class EngineParityError(Exception):
    pass


def run_engine_parity(hypothesis_id: str, *, jesse_metrics: dict[str, object] | None = None) -> dict[str, object]:
    prereg = load_preregistration(hypothesis_id)
    manifest_path = resolve_manifest_for_hypothesis(hypothesis_id, prereg)
    manifest = load_data_manifest(manifest_path)
    costs = manifest.get("costs")
    if not isinstance(costs, dict):
        raise EngineParityError("manifest costs block required")

    fee_bps = float(costs.get("fee_bps_per_side", 0))
    slip_bps = float(costs.get("slippage_bps_per_side", 0))

    primary = primary_buy_hold_net_return(
        fee_bps_per_side=fee_bps,
        slippage_bps_per_side=slip_bps,
    )
    if jesse_metrics is not None:
        secondary = jesse_metrics
    else:
        try:
            secondary = jesse_golden_slice_net_return(
                fee_bps_per_side=fee_bps,
                slippage_bps_per_side=slip_bps,
            )
        except JesseAdapterError as exc:
            raise EngineParityError(str(exc)) from exc

    primary_net = float(primary["net_return"])
    secondary_net = float(secondary["net_return"])
    max_abs_delta = abs(primary_net - secondary_net)

    cfg = prereg.get("engine_parity") if isinstance(prereg, dict) else None
    limit = 0.01
    if isinstance(cfg, dict) and cfg.get("max_metric_delta") is not None:
        limit = float(cfg["max_metric_delta"])

    status = "pass" if max_abs_delta <= limit else "fail"
    report = {
        "status": status,
        "method": "golden_slice_primary_vs_jesse_research",
        "metric": "net_return",
        "primary_engine": primary,
        "secondary_engine": secondary,
        "max_abs_delta": max_abs_delta,
        "max_metric_delta_limit": limit,
    }
    if status != "pass":
        raise EngineParityError(
            f"engine parity fail: delta {max_abs_delta} > {limit} "
            f"(primary={primary_net}, jesse={secondary_net})"
        )
    return report


def write_engine_parity_for_run(hypothesis_id: str, run_dir: Path, report: dict[str, object]) -> Path:
    out = run_dir / "engine_parity.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return out


def materialize_parity_run(hypothesis_id: str, *, jesse_metrics: dict[str, object] | None = None) -> Path:
    report = run_engine_parity(hypothesis_id, jesse_metrics=jesse_metrics)
    backtest_root = repo_root() / "backtests" / hypothesis_id
    backtest_root.mkdir(parents=True, exist_ok=True)
    runs = sorted(backtest_root.glob("run-*"))
    run_name = f"run-{len(runs) + 1:04d}"
    run_dir = backtest_root / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    metrics = {
        "hypothesis_id": hypothesis_id,
        "net_return": report["primary_engine"]["net_return"],
        "engine": "primary_golden_slice",
        "parity_method": report["method"],
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    write_engine_parity_for_run(hypothesis_id, run_dir, report)
    return run_dir
