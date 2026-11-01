from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from week_trader.brokers.alpaca_paper import AlpacaPaperError, submit_alpaca_paper_order
from week_trader.paper_account_guards import (
    PaperAccountGuardError,
    assert_account_halt_absent,
    enforce_shared_account_guards,
    record_fill_tag_submission,
)
from week_trader.paper_forward import append_forward_event, register_pending_order
from week_trader.gate_log import verify_gate_log_file
from week_trader.manifest import ManifestError, resolve_manifest_for_hypothesis, load_data_manifest
from week_trader.prereg import load_preregistration
from week_trader.util import load_json, repo_root, sha256_json


FetchPositions = Callable[..., list[dict[str, Any]]]
FetchOpenOrders = Callable[..., list[dict[str, Any]]]


class PaperOrderError(Exception):
    pass


def paper_order(
    order_intent_id: str,
    gate_log_path: Path,
    *,
    dry_run: bool = False,
    fetch_positions: FetchPositions | None = None,
    fetch_open_orders: FetchOpenOrders | None = None,
) -> dict[str, Any]:
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

    try:
        assert_account_halt_absent()
    except PaperAccountGuardError as exc:
        raise PaperOrderError(str(exc)) from exc

    limits_path = root / "risk_limits.json"
    limits = load_json(limits_path)
    _enforce_risk_limits(limits, hypothesis_id)

    venue = prereg.get("venue_contract", {})
    if venue.get("instrument_class") == "crypto_perp" and venue.get("paper_venue") == "alpaca_paper":
        raise PaperOrderError("Alpaca paper invalid for crypto_perp venue_contract")

    intent = _load_order_intent(hypothesis_id, order_intent_id)
    _validate_spot_intent(hypothesis_id, intent, prereg)
    paper_venue = venue.get("paper_venue")
    if paper_venue != "alpaca_paper":
        raise PaperOrderError(f"unsupported paper_venue {paper_venue!r}")

    try:
        guard_meta = enforce_shared_account_guards(
            hypothesis_id,
            intent,
            order_intent_id,
            fetch_positions=fetch_positions,
            fetch_open_orders=fetch_open_orders,
        )
    except PaperAccountGuardError as exc:
        raise PaperOrderError(str(exc)) from exc
    intent = {**intent, "client_order_id": guard_meta["client_order_id"]}

    result: dict[str, Any] = {
        "order_intent_id": order_intent_id,
        "hypothesis_id": hypothesis_id,
        "gate_log": str(gate_log_path.relative_to(root)),
        "broker_calls": 0,
        "status": "validated_dry_run" if dry_run else "pending_paper_submit",
        "fill_tag": guard_meta["fill_tag"],
        "client_order_id": guard_meta["client_order_id"],
        "projected_notional_usd": guard_meta["projected_notional_usd"],
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
        order_id = broker_resp.get("id")
        if isinstance(order_id, str):
            record_fill_tag_submission(
                hypothesis_id,
                client_order_id=str(guard_meta["client_order_id"]),
                fill_tag=str(guard_meta["fill_tag"]),
                symbol=str(intent.get("symbol", "")),
                side=str(intent.get("side", "")),
                qty=str(intent.get("qty", "")),
                order_intent_id=order_intent_id,
            )
            register_pending_order(
                hypothesis_id,
                order_id,
                {
                    "order_intent_id": order_intent_id,
                    "gate_log": str(gate_log_path.relative_to(root)),
                    "fill_tag": guard_meta["fill_tag"],
                    "client_order_id": guard_meta["client_order_id"],
                },
            )
            append_forward_event(
                hypothesis_id,
                "order_submitted",
                {
                    "order_intent_id": order_intent_id,
                    "alpaca_order_id": order_id,
                    "symbol": broker_resp.get("symbol"),
                    "side": intent.get("side"),
                    "qty": intent.get("qty"),
                },
            )

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


def _validate_spot_intent(hypothesis_id: str, intent: dict[str, Any], prereg: dict[str, Any]) -> None:
    venue = prereg.get("venue_contract", {})
    if not isinstance(venue, dict):
        raise PaperOrderError("venue_contract missing")
    instrument_class = venue.get("instrument_class")
    if instrument_class not in {"crypto_spot", "equity"}:
        raise PaperOrderError("order intents require crypto_spot or equity venue_contract")
    symbol = intent.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        raise PaperOrderError("order intent symbol required")
    normalized = symbol.strip().upper()
    if instrument_class == "crypto_spot":
        perp_markers = ("PERP", "USDTM", "USDTP", "SWAP", "-P")
        if any(marker in normalized for marker in perp_markers):
            raise PaperOrderError("perp-like symbol forbidden on Alpaca spot paper rail")
    try:
        manifest_path = resolve_manifest_for_hypothesis(hypothesis_id, prereg)
        manifest = load_data_manifest(manifest_path)
    except ManifestError as exc:
        raise PaperOrderError(str(exc)) from exc
    if manifest.get("instrument_class") != instrument_class:
        raise PaperOrderError("manifest instrument_class must match venue_contract")
    universe = manifest.get("universe")
    if not isinstance(universe, dict):
        raise PaperOrderError("manifest universe missing")
    symbols = universe.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        raise PaperOrderError("manifest universe.symbols missing")
    allowed = {_manifest_symbol_to_alpaca(s) for s in symbols if isinstance(s, str)}
    if normalized not in allowed:
        raise PaperOrderError(f"symbol {normalized!r} not in manifest universe")


def _manifest_symbol_to_alpaca(manifest_symbol: str) -> str:
    return manifest_symbol.replace("/", "").upper()


def _enforce_risk_limits(limits: dict[str, Any], hypothesis_id: str) -> None:
    for key in ("max_position_notional_usd", "max_daily_loss_usd"):
        if key not in limits:
            raise PaperOrderError(f"risk_limits.json missing {key}")

    pattern = limits.get("kill_switch_file_pattern", "paper/{hypothesis_id}/HALT")
    halt_glob = pattern.format(hypothesis_id=hypothesis_id)
    halt_path = repo_root() / halt_glob
    if halt_path.exists():
        raise PaperOrderError("kill switch HALT engaged")
