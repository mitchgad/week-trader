from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from week_trader.manifest import (
    ManifestError,
    load_data_manifest,
    resolve_manifest_for_hypothesis,
    validate_manifest_costs,
)
from week_trader.paper_forward import FORWARD_STALE_STATUS_HOURS, read_last_signal_side
from week_trader.prereg import compute_freeze_hashes, load_preregistration
from week_trader.util import hypothesis_dir, load_json, repo_root, sha256_json


def build_jev_state(hypothesis_id: str, *, gate: str, metrics_path: Path | None = None) -> dict[str, Any]:
    """Assemble Jev state from frozen numeric fields only — no LLM prose."""
    prereg = load_preregistration(hypothesis_id)
    freeze_path = hypothesis_dir(hypothesis_id) / "freeze_manifest.json"
    freeze = load_json(freeze_path)

    metrics: dict[str, Any] = {}
    metrics_file: dict[str, Any] = {}
    if metrics_path and metrics_path.is_file():
        loaded = load_json(metrics_path)
        if isinstance(loaded, dict):
            metrics_file = loaded
            metrics = loaded.get("metrics", loaded)
            if not isinstance(metrics, dict):
                metrics = {}

    hashes = compute_freeze_hashes(hypothesis_id)
    halt_path = repo_root() / "paper" / hypothesis_id / "HALT"

    spec_fields = _spec_fields(hypothesis_id, prereg)
    forward_ops = _forward_operational_fields(hypothesis_id)

    data_fresh = (
        bool(metrics["data_fresh"])
        if "data_fresh" in metrics
        else forward_ops.get("data_fresh", False)
    )
    within_risk_bands = (
        bool(metrics["within_risk_bands"])
        if "within_risk_bands" in metrics
        else forward_ops.get("within_risk_bands", False)
    )
    risk_within_limits = (
        bool(metrics["risk_within_limits"])
        if "risk_within_limits" in metrics
        else forward_ops.get("within_risk_bands", False)
    )

    fields: dict[str, Any] = {
        "hypothesis_id": hypothesis_id,
        "gate": gate,
        "freeze_manifest_hash": sha256_json(freeze),
        "spec_has_universe_and_timing": _hypothesis_has_sections(hypothesis_id),
        "spec_has_cost_manifest_binding": bool(prereg.get("data_manifest_id")),
        **spec_fields,
        "implementation_audit_pass": metrics.get("implementation_audit_pass", False),
        "unit_tests_pass": metrics.get("unit_tests_pass", False),
        "data_fresh": data_fresh,
        "within_risk_bands": within_risk_bands,
        "halt_absent": not halt_path.exists(),
        "halt_reason_resolved": metrics.get("halt_reason_resolved", False),
        "risk_within_limits": risk_within_limits,
        "forward_monitor_present": forward_ops.get("forward_monitor_present", False),
        "forward_monitor_age_hours": forward_ops.get("forward_monitor_age_hours"),
        "last_signal_side": forward_ops.get("last_signal_side"),
        "btc_spot_open": forward_ops.get("btc_spot_open", False),
        "artifact_hashes": hashes,
    }

    state = {"fields": fields, "metrics": metrics_file if metrics_file else metrics}
    state["_state_hash"] = sha256_json({"fields": fields, "metrics": state["metrics"]})
    return state


def _spec_fields(hypothesis_id: str, prereg: dict[str, Any]) -> dict[str, Any]:
    venue = prereg.get("venue_contract", {})
    if not isinstance(venue, dict):
        venue = {}
    instrument = venue.get("instrument_class")
    manifest_instrument: str | None = None
    manifest_funding_null = False
    try:
        manifest_path = resolve_manifest_for_hypothesis(hypothesis_id, prereg)
        manifest = load_data_manifest(manifest_path)
        manifest_instrument = manifest.get("instrument_class")
        costs = manifest.get("costs")
        if isinstance(costs, dict):
            manifest_funding_null = costs.get("funding_series_id") in (None, "") and costs.get(
                "funding_interval_hours"
            ) in (None, "")
    except ManifestError:
        manifest_instrument = None
        manifest_funding_null = False

    spot_only = (
        instrument == "crypto_spot"
        and venue.get("paper_venue") == "alpaca_paper"
        and manifest_instrument == "crypto_spot"
        and manifest_funding_null
    )
    disconfirmers = _hypothesis_disconfirmers_ok(hypothesis_id)
    proof = _proof_contract_fields(prereg, hypothesis_id)
    cost_ok = False
    try:
        manifest_path = resolve_manifest_for_hypothesis(hypothesis_id, prereg)
        manifest = load_data_manifest(manifest_path)
        cost_ok = not validate_manifest_costs(manifest)
    except ManifestError:
        cost_ok = False
    engine_parity = bool((prereg.get("engine_parity") or {}).get("required_before_promotion"))
    return {
        "venue_contract_spot_only": spot_only,
        "disconfirmers_documented": disconfirmers,
        "manifest_cost_block_present": cost_ok,
        "engine_parity_required": engine_parity,
        **proof,
    }


def _proof_contract_fields(prereg: dict[str, Any], hypothesis_id: str) -> dict[str, Any]:
    proof = prereg.get("proof_contract")
    venue = prereg.get("venue_contract")
    if not isinstance(venue, dict):
        venue = {}
    if not isinstance(proof, dict):
        return {
            "proof_contract_present": False,
            "forbidden_perp_funding_proof_in_prereg": False,
            "promotion_proof_alpaca_spot_forward_only": False,
            "venue_contract_instrument_class": venue.get("instrument_class"),
            "venue_contract_paper_venue": venue.get("paper_venue"),
            "proof_forbidden_evidence_types": [],
            "perp_funding_proof_is_disconfirmer_kill": False,
            "backtest_metrics_do_not_satisfy_paper_proof": False,
            "spec_validation_proof_excerpt": None,
        }
    forbidden = proof.get("forbidden_promotion_evidence")
    if not isinstance(forbidden, list):
        forbidden = []
    allowed = proof.get("allowed_operational_proof")
    if not isinstance(allowed, list):
        allowed = []
    forbids_perp = any(
        isinstance(item, str) and "perp" in item.lower() for item in forbidden
    )
    forward_only = proof.get("operational_validation") == "alpaca_paper_crypto_spot_forward_only"
    spot_proof_allowed = any(
        isinstance(item, str) and "spot" in item.lower() for item in allowed
    )
    return {
        "proof_contract_present": True,
        "forbidden_perp_funding_proof_in_prereg": forbids_perp,
        "promotion_proof_alpaca_spot_forward_only": forward_only and spot_proof_allowed,
        "venue_contract_instrument_class": venue.get("instrument_class"),
        "venue_contract_paper_venue": venue.get("paper_venue"),
        "proof_forbidden_evidence_types": [item for item in forbidden if isinstance(item, str)],
        "perp_funding_proof_is_disconfirmer_kill": _hypothesis_perp_proof_kill_documented(
            hypothesis_id
        ),
        "backtest_metrics_do_not_satisfy_paper_proof": bool(
            proof.get("backtest_metrics_do_not_satisfy_paper_proof")
        ),
        "spec_validation_proof_excerpt": _validation_proof_excerpt(hypothesis_id),
    }


def _hypothesis_perp_proof_kill_documented(hypothesis_id: str) -> bool:
    path = hypothesis_dir(hypothesis_id) / "HYPOTHESIS.md"
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8").lower()
    if "## disconfirmers" not in text:
        return False
    dis_section = text[text.index("## disconfirmers") :]
    return "perp funding" in dis_section and ("kill" in dis_section or "falsif" in dis_section)


def _validation_proof_excerpt(hypothesis_id: str) -> str | None:
    path = hypothesis_dir(hypothesis_id) / "HYPOTHESIS.md"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    marker = "## Validation and promotion proof"
    lower = text.lower()
    if marker.lower() not in lower:
        return None
    start = lower.index(marker.lower())
    section = text[start : start + 1200]
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    excerpt = " ".join(lines[:8])
    return excerpt[:800] if excerpt else None


def _hypothesis_disconfirmers_ok(hypothesis_id: str) -> bool:
    path = hypothesis_dir(hypothesis_id) / "HYPOTHESIS.md"
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8").lower()
    if "## disconfirmers" not in text:
        return False
    dis_idx = text.index("## disconfirmers")
    dis_section = text[dis_idx:]
    proof_markers = ("perp funding", "perp", "funding p", "binance", "carry", "basis")
    return any(marker in dis_section for marker in proof_markers)


def _forward_operational_fields(hypothesis_id: str) -> dict[str, Any]:
    forward = repo_root() / "paper" / hypothesis_id / "forward"
    status_path = forward / "status.json"
    events_path = forward / "events.jsonl"
    out: dict[str, Any] = {
        "forward_monitor_present": False,
        "forward_monitor_age_hours": None,
        "last_signal_side": read_last_signal_side(events_path),
        "btc_spot_open": False,
        "data_fresh": False,
        "within_risk_bands": False,
    }
    if not status_path.is_file():
        return out

    loaded = load_json(status_path)
    if not isinstance(loaded, dict):
        return out

    out["forward_monitor_present"] = True
    ts_raw = loaded.get("timestamp_utc")
    age_hours = _age_hours(ts_raw) if isinstance(ts_raw, str) else None
    out["forward_monitor_age_hours"] = age_hours
    if age_hours is not None and age_hours <= FORWARD_STALE_STATUS_HOURS:
        out["data_fresh"] = True

    btc = loaded.get("btc_spot_position")
    if isinstance(btc, dict):
        out["btc_spot_open"] = bool(btc.get("open"))

    side = loaded.get("last_signal_side")
    if isinstance(side, str):
        out["last_signal_side"] = side

    out["within_risk_bands"] = _within_risk_bands_from_status(loaded)
    return out


def _within_risk_bands_from_status(status: dict[str, Any]) -> bool:
    limits_path = repo_root() / "risk_limits.json"
    if not limits_path.is_file():
        return False
    limits = load_json(limits_path)
    if not isinstance(limits, dict):
        return False

    equity = _float_or_none(status.get("account_equity"))
    if equity is None or equity <= 0:
        return False

    last_equity = _float_or_none(status.get("last_equity"))
    max_daily_loss = _float_or_none(limits.get("max_daily_loss_usd"))
    if last_equity is not None and max_daily_loss is not None and last_equity > equity:
        daily_loss = last_equity - equity
        if daily_loss > max_daily_loss:
            return False

    max_notional = _float_or_none(limits.get("max_position_notional_usd"))
    btc = status.get("btc_spot_position")
    if isinstance(btc, dict) and max_notional is not None:
        market_value = _float_or_none(btc.get("market_value"))
        if market_value is not None and market_value > max_notional:
            return False

    return True


def _hypothesis_has_sections(hypothesis_id: str) -> bool:
    path = hypothesis_dir(hypothesis_id) / "HYPOTHESIS.md"
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8").lower()
    required = ("universe", "venue contract", "costs", "signal")
    return all(section in text for section in required)


def _hypothesis_has_disconfirmers(hypothesis_id: str) -> bool:
    return _hypothesis_disconfirmers_ok(hypothesis_id)


def _age_hours(timestamp_utc: str) -> float | None:
    try:
        ts = datetime.strptime(timestamp_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    delta = datetime.now(timezone.utc) - ts
    return delta.total_seconds() / 3600.0


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def write_state_artifact(hypothesis_id: str, gate: str, out_path: Path, metrics_path: Path | None) -> dict[str, Any]:
    state = build_jev_state(hypothesis_id, gate=gate, metrics_path=metrics_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return state
