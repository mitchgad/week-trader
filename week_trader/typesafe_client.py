from __future__ import annotations

import os
from typing import Any

import requests

from week_trader.gate_log import GateLogError


TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
REQUEST_TIMEOUT_SECONDS = 30


class TypeSafeError(Exception):
    pass


def call_system_one(
    *,
    model_id: str,
    state: dict[str, Any],
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Only invoked from jev-gate pipeline."""
    if model_id == "jev-latest":
        raise TypeSafeError("jev-latest is forbidden")

    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise TypeSafeError("TYPESAFE_API_KEY missing — fail closed")

    payload = {
        "model": model_id,
        "state": _state_for_api(state),
        "questions": questions,
    }

    try:
        response = requests.post(
            TYPESAFE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise TypeSafeError("TypeSafe API timeout — fail closed") from exc
    except requests.RequestException as exc:
        raise TypeSafeError(f"TypeSafe API error — fail closed: {exc}") from exc

    if response.status_code >= 400:
        raise TypeSafeError(f"TypeSafe HTTP {response.status_code} — fail closed")

    try:
        body = response.json()
    except ValueError as exc:
        raise TypeSafeError("TypeSafe malformed JSON — fail closed") from exc

    if not isinstance(body, dict):
        raise TypeSafeError("TypeSafe response must be object — fail closed")

    return body


def _state_for_api(state: dict[str, Any]) -> dict[str, Any]:
    cleaned = {k: v for k, v in state.items() if not str(k).startswith("_")}
    return cleaned


def compare_thresholds(
    gate: str,
    prereg: dict[str, Any],
    response: dict[str, Any],
    questions: list[dict[str, Any]],
) -> tuple[bool, dict[str, Any]]:
    thresholds = prereg.get("thresholds", {})
    details: dict[str, Any] = {"gate": gate, "comparisons": []}
    answers = response.get("answers") or response.get("probabilities") or response

    passed = True
    for question in questions:
        qid = question["id"]
        qtype = question["type"]
        entry: dict[str, Any] = {"question_id": qid, "type": qtype}

        if qtype == "score":
            min_key = "backtest_promotion_min_score" if gate == "backtest" else "spec_pass_min_probability"
            min_score = float(thresholds.get(min_key, 1.0))
            prob = _extract_probability(answers, qid)
            entry["probability"] = prob
            entry["min_required"] = min_score
            ok = prob is not None and prob >= min_score
        elif qtype == "choice":
            min_prob = float(thresholds.get("trade_gate_min_probability", 0.7))
            prob = _extract_probability(answers, qid)
            entry["probability"] = prob
            entry["min_required"] = min_prob
            ok = prob is not None and prob >= min_prob
        elif qtype == "noul":
            min_prob = float(thresholds.get("spec_pass_min_probability", 0.65))
            prob = _extract_probability(answers, qid)
            entry["probability"] = prob
            entry["min_required"] = min_prob
            ok = prob is not None and prob >= min_prob
        else:
            ok = False
            entry["error"] = "unknown question type"

        entry["pass"] = ok
        details["comparisons"].append(entry)
        passed = passed and ok

    details["pass"] = passed
    return passed, details


def _extract_probability(answers: Any, qid: str) -> float | None:
    if isinstance(answers, dict):
        if qid in answers:
            val = answers[qid]
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, dict) and "probability" in val:
                return float(val["probability"])
    return None
