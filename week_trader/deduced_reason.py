from __future__ import annotations

from typing import Any

from week_trader.typesafe_client import compare_thresholds


def build_deduced_reason(
    *,
    gate: str,
    prereg: dict[str, Any],
    state: dict[str, Any],
    questions: list[dict[str, Any]],
    response: dict[str, Any],
    threshold_compare: dict[str, Any],
) -> dict[str, Any]:
    """
    Deterministic explanation from frozen question state_keys and actual inputs.
    Labelled deduced — not Jev's own rationale.
    """
    comparisons = threshold_compare.get("comparisons")
    if not isinstance(comparisons, list):
        _, threshold_compare = compare_thresholds(gate, prereg, response, questions)
        comparisons = threshold_compare.get("comparisons", [])

    question_inputs: list[dict[str, Any]] = []
    failing_inputs: list[str] = []
    for question in questions:
        qid = question.get("id")
        if not isinstance(qid, str):
            continue
        keys = question.get("state_keys")
        if not isinstance(keys, list):
            continue
        for key in keys:
            if not isinstance(key, str):
                continue
            value = _resolve_state_key(state, key)
            in_band, reason = _input_in_band(value)
            entry = {
                "state_key": key,
                "question_id": qid,
                "value": value,
                "in_band": in_band,
            }
            if reason:
                entry["band_reason"] = reason
            question_inputs.append(entry)
            if not in_band:
                failing_inputs.append(f"{key}={value!r} ({reason or 'out_of_band'})")

    all_declared_in_band = len(failing_inputs) == 0
    gate_pass = threshold_compare.get("pass") is True

    summary_parts: list[str] = []
    if failing_inputs:
        summary_parts.append(
            "Declared question inputs false, missing, or out of band: "
            + "; ".join(failing_inputs)
        )
    elif not gate_pass:
        summary_parts.append(
            "All declared question inputs present and in band; Jev scored below the preregistered threshold."
        )
    else:
        summary_parts.append("Declared question inputs present and in band; threshold compare passed.")

    failed_questions: list[str] = []
    for comp in comparisons:
        if isinstance(comp, dict) and comp.get("pass") is False:
            qid = comp.get("question_id")
            prob = comp.get("probability")
            minimum = comp.get("min_required")
            if isinstance(qid, str):
                failed_questions.append(
                    f"{qid}: probability={prob} min_required={minimum}"
                )

    return {
        "label": "deduced",
        "summary": " ".join(summary_parts),
        "all_declared_inputs_in_band": all_declared_in_band,
        "gate_pass": gate_pass,
        "inputs": question_inputs,
        "threshold_failures": failed_questions,
    }


def _resolve_state_key(state: dict[str, Any], dotted: str) -> Any:
    parts = dotted.split(".")
    current: Any = state
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _input_in_band(value: Any) -> tuple[bool, str | None]:
    if value is None:
        return False, "missing"
    if value == "unknown":
        return False, "unknown"
    if isinstance(value, bool):
        return value, None if value else "false"
    if isinstance(value, (int, float)):
        return True, None
    if isinstance(value, str):
        if not value.strip():
            return False, "empty"
        return True, None
    return True, None
