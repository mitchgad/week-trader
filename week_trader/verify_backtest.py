from __future__ import annotations

import json
from pathlib import Path

from week_trader.manifest import resolve_manifest_for_hypothesis, validate_manifest_costs, load_data_manifest
from week_trader.prereg import load_preregistration
from week_trader.util import hypothesis_dir, load_json, repo_root


class VerifyBacktestError(Exception):
    pass


def verify_backtest(hypothesis_id: str) -> dict[str, object]:
    prereg = load_preregistration(hypothesis_id)
    manifest_path = resolve_manifest_for_hypothesis(hypothesis_id, prereg)
    manifest = load_data_manifest(manifest_path)
    errors = validate_manifest_costs(manifest)
    if errors:
        raise VerifyBacktestError("cost/PIT manifest errors: " + "; ".join(errors))

    freeze_path = hypothesis_dir(hypothesis_id) / "freeze_manifest.json"
    if not freeze_path.is_file():
        raise VerifyBacktestError("freeze_manifest.json required before backtest")

    backtest_root = repo_root() / "backtests" / hypothesis_id
    if not backtest_root.is_dir():
        raise VerifyBacktestError(f"no backtests/{hypothesis_id}/ directory")

    runs = sorted(backtest_root.glob("run-*"))
    if not runs:
        raise VerifyBacktestError("no run-* directories")

    latest = runs[-1]
    metrics_path = latest / "metrics.json"
    if not metrics_path.is_file():
        raise VerifyBacktestError("metrics.json missing in latest run")

    metrics = load_json(metrics_path)
    parity = _check_engine_parity(hypothesis_id, latest, prereg, metrics)
    if not parity["ok"]:
        raise VerifyBacktestError(parity["reason"])

    return {
        "hypothesis_id": hypothesis_id,
        "run": latest.name,
        "manifest": str(manifest_path.relative_to(repo_root())),
        "engine_parity": parity,
        "status": "verify_backtest_ok_scaffold",
    }


def _check_engine_parity(
    hypothesis_id: str,
    run_dir: Path,
    prereg: dict[str, object],
    metrics: dict[str, object],
) -> dict[str, object]:
    cfg = prereg.get("engine_parity") if isinstance(prereg, dict) else None
    if not isinstance(cfg, dict) or not cfg.get("required_before_promotion"):
        return {"ok": True, "reason": "parity not required"}

    parity_path = run_dir / "engine_parity.json"
    if not parity_path.is_file():
        return {
            "ok": False,
            "reason": "engine_parity.json missing — second engine or golden slice required",
        }

    parity = load_json(parity_path)
    if parity.get("status") != "pass":
        return {"ok": False, "reason": "engine_parity.json status must be pass"}

    max_delta = float(cfg.get("max_metric_delta", 0.01))
    delta = float(parity.get("max_abs_delta", 1.0))
    if delta > max_delta:
        return {"ok": False, "reason": f"parity delta {delta} exceeds {max_delta}"}

    return {"ok": True, "reason": "parity pass", "details": parity}
