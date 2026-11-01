from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from week_trader.brokers.alpaca_paper import AlpacaPaperError, paper_base_url
from week_trader.jev_gate import JevGateError, run_jev_gate
from week_trader.paper_order import PaperOrderError, paper_order
from week_trader.signal_intent import signal_is_flat, signal_matches_order_intent
from week_trader.util import load_json, repo_root

RunJevGate = Callable[[str, str], Path]
PaperOrderFn = Callable[..., dict[str, Any]]


class PaperForwardOrderError(Exception):
    pass


def list_order_intent_files(hypothesis_id: str) -> list[tuple[str, dict[str, Any]]]:
    intents_dir = repo_root() / "paper" / hypothesis_id / "intents"
    if not intents_dir.is_dir():
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(intents_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        data = load_json(path)
        if isinstance(data, dict):
            out.append((path.stem, data))
    return out


def resolve_order_intent_for_signal(
    hypothesis_id: str, signal: dict[str, Any]
) -> tuple[str, dict[str, Any]] | None:
    for intent_id, intent in list_order_intent_files(hypothesis_id):
        if signal_matches_order_intent(signal, intent):
            return intent_id, intent
    return None


def assert_alpaca_paper_host_pinned() -> str:
    """Fail closed unless Alpaca trading host is paper-api only."""
    try:
        return paper_base_url()
    except AlpacaPaperError as exc:
        raise PaperForwardOrderError(str(exc)) from exc


def submit_paper_order_for_signal(
    hypothesis_id: str,
    signal: dict[str, Any],
    *,
    dry_run: bool = False,
    run_jev_gate_fn: RunJevGate | None = None,
    paper_order_fn: PaperOrderFn | None = None,
    fetch_positions: Any = None,
    fetch_open_orders: Any = None,
) -> dict[str, Any]:
    """
    After a forward signal: trade gate (Jev) then paper-order when signal matches intent.
    Flat signals never submit. No side path around guards or gate validation.
    """
    if signal_is_flat(signal):
        return {"submitted": False, "reason": "flat_signal_no_order"}

    resolved = resolve_order_intent_for_signal(hypothesis_id, signal)
    if resolved is None:
        return {"submitted": False, "reason": "no_matching_order_intent"}

    intent_id, _intent = resolved
    assert_alpaca_paper_host_pinned()

    gate_runner = run_jev_gate_fn or run_jev_gate
    order_runner = paper_order_fn or paper_order

    try:
        gate_log_path = gate_runner(hypothesis_id, "trade")
    except JevGateError as exc:
        raise PaperForwardOrderError(str(exc)) from exc

    gate_log = load_json(gate_log_path)
    if gate_log.get("pass") is not True:
        return {
            "submitted": False,
            "reason": "trade_gate_did_not_pass",
            "gate_log": str(gate_log_path.relative_to(repo_root())),
            "order_intent_id": intent_id,
        }

    try:
        order_result = order_runner(
            intent_id,
            gate_log_path,
            dry_run=dry_run,
            fetch_positions=fetch_positions,
            fetch_open_orders=fetch_open_orders,
        )
    except PaperOrderError as exc:
        return {
            "submitted": False,
            "reason": "paper_order_rejected",
            "detail": str(exc),
            "order_intent_id": intent_id,
            "gate_log": str(gate_log_path.relative_to(repo_root())),
        }

    return {
        "submitted": not dry_run and order_result.get("status") == "submitted_paper",
        "validated_dry_run": dry_run and order_result.get("dry_run") is True,
        "order_intent_id": intent_id,
        "gate_log": str(gate_log_path.relative_to(repo_root())),
        "paper_order": order_result,
    }


def attach_order_submission(
    hypothesis_id: str,
    signal: dict[str, Any],
    recorded: dict[str, Any],
    *,
    submit_order: bool,
    dry_run: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    out = {**recorded, "signal": signal}
    if not submit_order:
        out["order_submission"] = {"submitted": False, "reason": "submit_order_disabled"}
        return out
    out["order_submission"] = submit_paper_order_for_signal(
        hypothesis_id, signal, dry_run=dry_run, **kwargs
    )
    return out
