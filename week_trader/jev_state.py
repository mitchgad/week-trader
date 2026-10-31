from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from week_trader.prereg import compute_freeze_hashes, load_preregistration
from week_trader.util import hypothesis_dir, load_json, sha256_json


def build_jev_state(hypothesis_id: str, *, gate: str, metrics_path: Path | None = None) -> dict[str, Any]:
    """Assemble Jev state from frozen numeric fields only — no LLM prose."""
    prereg = load_preregistration(hypothesis_id)
    freeze_path = hypothesis_dir(hypothesis_id) / "freeze_manifest.json"
    freeze = load_json(freeze_path)

    metrics: dict[str, Any] = {}
    if metrics_path and metrics_path.is_file():
        loaded = load_json(metrics_path)
        if isinstance(loaded, dict):
            metrics = loaded.get("metrics", loaded)

    hashes = compute_freeze_hashes(hypothesis_id)
    halt_path = Path("paper") / hypothesis_id / "HALT"
    if not halt_path.is_absolute():
        halt_path = hypothesis_dir(hypothesis_id).parent.parent / halt_path

    fields: dict[str, Any] = {
        "hypothesis_id": hypothesis_id,
        "gate": gate,
        "freeze_manifest_hash": sha256_json(freeze),
        "spec_has_universe_and_timing": _hypothesis_has_sections(hypothesis_id),
        "spec_has_cost_manifest_binding": bool(prereg.get("data_manifest_id")),
        "implementation_audit_pass": metrics.get("implementation_audit_pass", False),
        "unit_tests_pass": metrics.get("unit_tests_pass", False),
        "data_fresh": metrics.get("data_fresh", False),
        "within_risk_bands": metrics.get("within_risk_bands", False),
        "halt_absent": not halt_path.exists(),
        "halt_reason_resolved": metrics.get("halt_reason_resolved", False),
        "risk_within_limits": metrics.get("risk_within_limits", False),
        "artifact_hashes": hashes,
    }

    state = {"fields": fields, "metrics": metrics}
    state["_state_hash"] = sha256_json({"fields": fields, "metrics": metrics})
    return state


def _hypothesis_has_sections(hypothesis_id: str) -> bool:
    path = hypothesis_dir(hypothesis_id) / "HYPOTHESIS.md"
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8").lower()
    required = ("universe", "venue contract", "costs", "signal")
    return all(section in text for section in required)


def write_state_artifact(hypothesis_id: str, gate: str, out_path: Path, metrics_path: Path | None) -> dict[str, Any]:
    state = build_jev_state(hypothesis_id, gate=gate, metrics_path=metrics_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return state
