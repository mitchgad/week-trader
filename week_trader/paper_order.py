from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from week_trader.brokers.alpaca_paper import AlpacaPaperError, submit_alpaca_paper_order
from week_trader.gate_log import verify_gate_log_file
from week_trader.prereg import load_preregistration
from week_trader.util import load_json, repo_root, sha256_json


class PaperOrderError(Exception):
    pass


def paper_order(order_intent_id: str, gate_log_path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Validate gate + risk + HALT before any Alpaca paper broker call."""
    root = repo_root()
    ok, reason = verify_gate_log_file(gate_log_path)
    if not ok:
        raise PaperOrderError(f"invalid gate log: {reason}")

    gate_log = load_json(gate_log_path)
    hypothesis_id = gate_log["hypothesis_id"]
    if gate_log.get("gate") != "trade":
        raise PaperOrderError("gate log must be trade gate")
    if gate_log.get("pass") is not True:
        raise PaperOrderError("trade gate did not pass")

    prereg = load_preregistration(hypothesis_id)
    max_age = int(prereg.get("max_gate_age_minutes", 15))
    ts = datetime.strptime(gate_log["timestamp_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    age_min = (datetime.now(timezone.utc) - ts).total_seconds() / 60.0
    if age_min > max_age:
        raise PaperOrderError(f"gate log stale: {age_min:.1f}m > {max_age}m")

    freeze_path = root / "hypotheses" / hypothesis_id / "freeze_manifest.json"
    freeze_hash = sha256_json(load_json(freeze_path))
    if gate_log.get("freeze_manifest_hash") != freeze_hash:
        raise PaperOrderError("freeze_manifest_hash mismatch")

    halt_path = root / "paper" / hypothesis_id / "HALT"
    if halt_path.exists():
        raise PaperOrderError("HALT present — zero orders")

    limits_path = root / "risk_limits.json"
    limits = load_json(limits_path)
    _enforce_risk_limits(limits, hypothesis_id)

    venue = prereg.get("venue_contract", {})
    if venue.get("instrument_class") == "crypto_perp" and venue.get("paper_venue") == "alpaca_paper":
        raise PaperOrderError("Alpaca paper invalid for crypto_perp venue_contract")

    intent = _load_order_intent(hypothesis_id, order_intent_id)
    paper_venue = venue.get("paper_venue")
    if paper_venue != "alpaca_paper":
        raise PaperOrderError(f"unsupported paper_venue {paper_venue!r}")

    result: dict[str, Any] = {
        "order_intent_id": order_intent_id,
        "hypothesis_id": hypothesis_id,
        "gate_log": str(gate_log_path.relative_to(root)),
        "broker_calls": 0,
        "status": "validated_dry_run" if dry_run else "pending_paper_submit",
    }

    if dry_run:
        result["dry_run"] = True
    else:
        try:
            broker_resp = submit_alpaca_paper_order(intent=intent)
        except AlpacaPaperError as exc:
            raise PaperOrderError(str(exc)) from exc
        result["broker_calls"] = 1
        result["status"] = "submitted_paper"
        result["alpaca_order_id"] = broker_resp.get("id")
        result["broker_response"] = {
            "id": broker_resp.get("id"),
            "status": broker_resp.get("status"),
            "symbol": broker_resp.get("symbol"),
        }

    journal_dir = root / "paper" / hypothesis_id / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)
    log_path = journal_dir / "order-intents.jsonl"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, sort_keys=True) + "\n")

    return result


def _load_order_intent(hypothesis_id: str, order_intent_id: str) -> dict[str, Any]:
    path = repo_root() / "paper" / hypothesis_id / "intents" / f"{order_intent_id}.json"
    if not path.is_file():
        raise PaperOrderError(f"order intent not found: {path.relative_to(repo_root())}")
    data = load_json(path)
    if not isinstance(data, dict):
        raise PaperOrderError("order intent must be a JSON object")
    return data


def _enforce_risk_limits(limits: dict[str, Any], hypothesis_id: str) -> None:
    for key in ("max_position_notional_usd", "max_daily_loss_usd"):
        if key not in limits:
            raise PaperOrderError(f"risk_limits.json missing {key}")

    pattern = limits.get("kill_switch_file_pattern", "paper/{hypothesis_id}/HALT")
    halt_glob = pattern.format(hypothesis_id=hypothesis_id)
    halt_path = repo_root() / halt_glob
    if halt_path.exists():
        raise PaperOrderError("kill switch HALT engaged")
