from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from week_trader.util import load_json, repo_root, sha256_json


GATE_LOG_FIELDS = (
    "hypothesis_id",
    "gate",
    "freeze_manifest_hash",
    "state_hash",
    "request_hash",
    "response_body_hash",
    "model_id",
    "timestamp_utc",
    "pass",
    "threshold_compare",
)


def hmac_secret() -> bytes | None:
    raw = os.environ.get("GATE_LOG_HMAC_SECRET")
    if not raw:
        return None
    return raw.encode("utf-8")


def canonical_gate_payload(payload: dict[str, Any]) -> str:
    subset = {key: payload[key] for key in GATE_LOG_FIELDS if key in payload}
    return json.dumps(subset, sort_keys=True, separators=(",", ":"))


def sign_gate_log(payload: dict[str, Any]) -> str:
    secret = hmac_secret()
    if secret is None:
        raise GateLogError("GATE_LOG_HMAC_SECRET missing — cannot sign gate log")
    message = canonical_gate_payload(payload).encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_gate_log_file(path: Path) -> tuple[bool, str]:
    try:
        payload = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"invalid JSON: {exc}"

    for field in GATE_LOG_FIELDS:
        if field not in payload:
            return False, f"missing field: {field}"

    if payload.get("model_id") == "jev-latest":
        return False, "forbidden model_id jev-latest"

    signature = payload.get("log_signature")
    if not isinstance(signature, str):
        return False, "missing log_signature"

    secret = hmac_secret()
    if secret is None:
        return False, "GATE_LOG_HMAC_SECRET missing — cannot verify"

    expected = hmac.new(
        secret, canonical_gate_payload(payload).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False, "log_signature mismatch"

    gates_root = repo_root() / "gates"
    try:
        path.resolve().relative_to(gates_root.resolve())
    except ValueError:
        return False, "gate log must live under gates/"

    return True, "ok"


def write_gate_log(
    hypothesis_id: str,
    gate: str,
    *,
    freeze_manifest_hash: str,
    state_hash: str,
    request_hash: str,
    response_body_hash: str,
    model_id: str,
    passed: bool,
    threshold_compare: dict[str, Any],
    response_body: dict[str, Any],
    deduced_reason: dict[str, Any] | None = None,
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload: dict[str, Any] = {
        "hypothesis_id": hypothesis_id,
        "gate": gate,
        "freeze_manifest_hash": freeze_manifest_hash,
        "state_hash": state_hash,
        "request_hash": request_hash,
        "response_body_hash": response_body_hash,
        "model_id": model_id,
        "timestamp_utc": timestamp,
        "pass": passed,
        "threshold_compare": threshold_compare,
        "response": response_body,
    }
    if deduced_reason is not None:
        payload["deduced_reason"] = deduced_reason
    payload["log_signature"] = sign_gate_log(payload)

    out_dir = repo_root() / "gates" / hypothesis_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"jev-{gate}-{timestamp.replace(':', '')}.json"
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return out_path


class GateLogError(Exception):
    pass
