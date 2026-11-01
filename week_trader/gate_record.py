from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from week_trader.util import repo_root, sha256_json

SECRET_KEY_PATTERN = re.compile(r"(api[_-]?key|secret|authorization|password|token)", re.I)


class GateRecordError(Exception):
    pass


def records_path(hypothesis_id: str) -> Path:
    return repo_root() / "gates" / hypothesis_id / "jev-records.jsonl"


def sanitize_for_record(obj: Any) -> Any:
    """Remove secret-like keys from nested structures."""
    if isinstance(obj, dict):
        cleaned: dict[str, Any] = {}
        for key, value in obj.items():
            if SECRET_KEY_PATTERN.search(str(key)):
                continue
            cleaned[key] = sanitize_for_record(value)
        return cleaned
    if isinstance(obj, list):
        return [sanitize_for_record(item) for item in obj]
    return obj


def verify_record_hashes(record: dict[str, Any]) -> tuple[bool, str]:
    request_body = record.get("request_body")
    state = record.get("state")
    if not isinstance(request_body, dict) or not isinstance(state, dict):
        return False, "request_body and state must be objects"
    expected_request = record.get("request_hash")
    expected_state = record.get("state_hash")
    if not isinstance(expected_request, str) or not isinstance(expected_state, str):
        return False, "request_hash and state_hash required"
    actual_request = sha256_json(request_body)
    state_for_hash = {k: v for k, v in state.items() if not str(k).startswith("_")}
    metrics = state_for_hash.get("metrics")
    fields = state_for_hash.get("fields")
    if not isinstance(metrics, dict):
        metrics = {}
    if not isinstance(fields, dict):
        fields = {}
    actual_state = sha256_json({"fields": fields, "metrics": metrics})
    if actual_request != expected_request:
        return False, "request_hash mismatch"
    if actual_state != expected_state:
        return False, "state_hash mismatch"
    return True, "ok"


def append_gate_record(
    *,
    hypothesis_id: str,
    gate: str,
    gate_log_path: Path,
    freeze_manifest_hash: str,
    state: dict[str, Any],
    request_body: dict[str, Any],
    request_hash: str,
    state_hash: str,
    response_body_hash: str,
    model_id: str,
    passed: bool,
    threshold_compare: dict[str, Any],
    response_body: dict[str, Any],
    deduced_reason: dict[str, Any],
    deployed_git_sha: str,
    ci_evidence_meta: dict[str, Any],
) -> Path:
    if deduced_reason.get("label") != "deduced":
        raise GateRecordError("deduced_reason must be labelled deduced")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fields = state.get("fields") if isinstance(state.get("fields"), dict) else {}
    signal = {
        "last_signal_side": fields.get("last_signal_side"),
        "signal_matches_intent": fields.get("signal_matches_intent"),
        "order_intent_id": fields.get("order_intent_id"),
        "order_intent_side": fields.get("order_intent_side"),
        "order_intent_symbol": fields.get("order_intent_symbol"),
    }

    record: dict[str, Any] = sanitize_for_record(
        {
            "record_version": 1,
            "timestamp_utc": timestamp,
            "hypothesis_id": hypothesis_id,
            "gate": gate,
            "strategy": hypothesis_id,
            "signal": signal,
            "deployed_git_sha": deployed_git_sha,
            "freeze_manifest_hash": freeze_manifest_hash,
            "request_hash": request_hash,
            "state_hash": state_hash,
            "response_body_hash": response_body_hash,
            "model_id": model_id,
            "pass": passed,
            "threshold_compare": threshold_compare,
            "request_body": request_body,
            "state": state_for_record(state),
            "response_raw": response_body,
            "deduced_reason": deduced_reason,
            "ci_evidence": ci_evidence_meta,
            "gate_log_path": str(gate_log_path.relative_to(repo_root())),
        }
    )

    ok, reason = verify_record_hashes(record)
    if not ok:
        raise GateRecordError(reason)

    out_path = records_path(hypothesis_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True, separators=(",", ":"))
    with out_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return out_path


def state_for_record(state: dict[str, Any]) -> dict[str, Any]:
    cleaned = sanitize_for_record({k: v for k, v in state.items() if not str(k).startswith("_")})
    if isinstance(cleaned, dict):
        return cleaned
    return {}


def read_gate_records(hypothesis_id: str) -> list[dict[str, Any]]:
    path = records_path(hypothesis_id)
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        loaded = json.loads(line)
        if isinstance(loaded, dict):
            records.append(loaded)
    return records
