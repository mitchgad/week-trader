from __future__ import annotations

from pathlib import Path
from typing import Any

from week_trader.gate_log import GateLogError, write_gate_log
from week_trader.jev_state import build_jev_state
from week_trader.manifest import ManifestError, resolve_manifest_for_hypothesis, validate_manifest_costs
from week_trader.manifest import load_data_manifest
from week_trader.prereg import compute_freeze_hashes, load_preregistration
from week_trader.typesafe_client import TypeSafeError, call_system_one, compare_thresholds
from week_trader.util import load_json, sha256_json


class JevGateError(Exception):
    pass


def run_jev_gate(hypothesis_id: str, gate: str, *, metrics_path: Path | None = None) -> Path:
    prereg = load_preregistration(hypothesis_id)
    model_id = prereg.get("model_id")
    if not model_id or model_id == "jev-latest":
        raise JevGateError("invalid or forbidden model_id in preregistration")

    questions_map = prereg.get("jev_questions", {})
    questions = questions_map.get(gate)
    if not questions:
        raise JevGateError(f"no jev_questions for gate {gate!r}")

    from week_trader.util import hypothesis_dir

    freeze_path = hypothesis_dir(hypothesis_id) / "freeze_manifest.json"
    if not freeze_path.is_file():
        raise JevGateError("freeze_manifest.json required before any Jev call")

    manifest_path = resolve_manifest_for_hypothesis(hypothesis_id, prereg)
    manifest = load_data_manifest(manifest_path)
    cost_errors = validate_manifest_costs(manifest)
    if cost_errors:
        raise JevGateError("manifest cost/PIT errors: " + "; ".join(cost_errors))

    state = build_jev_state(hypothesis_id, gate=gate, metrics_path=metrics_path)
    state_hash = state.get("_state_hash") or sha256_json(state)
    freeze = load_json(freeze_path)
    freeze_hash = sha256_json(freeze)

    request_body = {
        "model_id": model_id,
        "gate": gate,
        "state": {k: v for k, v in state.items() if not str(k).startswith("_")},
        "questions": questions,
    }
    request_hash = sha256_json(request_body)

    try:
        response = call_system_one(model_id=model_id, state=state, questions=questions)
    except TypeSafeError as exc:
        raise JevGateError(str(exc)) from exc

    passed, threshold_compare = compare_thresholds(gate, prereg, response, questions)
    response_hash = sha256_json(response)

    try:
        return write_gate_log(
            hypothesis_id,
            gate,
            freeze_manifest_hash=freeze_hash,
            state_hash=str(state_hash),
            request_hash=request_hash,
            response_body_hash=response_hash,
            model_id=str(model_id),
            passed=passed,
            threshold_compare=threshold_compare,
            response_body=response,
        )
    except GateLogError as exc:
        raise JevGateError(str(exc)) from exc
