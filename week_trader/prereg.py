from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from week_trader.util import hypothesis_dir, load_json, sha256_file


SUBJECTIVE_PATTERN = re.compile(
    r"\b(clearly|obviously|good|bad|nice|strong|weak|probably|maybe)\b",
    re.IGNORECASE,
)


def lint_jev_questions(prereg: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    model_id = prereg.get("model_id")
    if model_id == "jev-latest":
        errors.append("model_id must not be jev-latest")
    if not model_id:
        errors.append("model_id is required")

    questions_root = prereg.get("jev_questions")
    if not isinstance(questions_root, dict) or not questions_root:
        errors.append("jev_questions must be a non-empty object")
        return errors

    for gate_name, questions in questions_root.items():
        if not isinstance(questions, list) or not questions:
            errors.append(f"gate {gate_name}: questions must be a non-empty list")
            continue
        for question in questions:
            errors.extend(_lint_one_question(gate_name, question))
    return errors


def _lint_one_question(gate_name: str, question: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    qid = question.get("id", "?")
    prefix = f"gate {gate_name} question {qid}"

    text = question.get("text", "")
    if not isinstance(text, str) or len(text) < 20:
        errors.append(f"{prefix}: text too short or missing")
    if SUBJECTIVE_PATTERN.search(text):
        errors.append(f"{prefix}: subjective wording forbidden")

    state_keys = question.get("state_keys")
    if not isinstance(state_keys, list) or not state_keys:
        errors.append(f"{prefix}: state_keys must list named schema keys")
    else:
        for key in state_keys:
            if not isinstance(key, str) or not key.startswith(("metrics.", "fields.")):
                errors.append(f"{prefix}: state_key {key!r} must start with metrics. or fields.")

    qtype = question.get("type")
    match qtype:
        case "choice":
            choices = question.get("choices")
            if not isinstance(choices, list) or len(choices) < 2:
                errors.append(f"{prefix}: choice questions need choices[]")
        case "score" | "noul":
            pass
        case _:
            errors.append(f"{prefix}: unknown type {qtype!r}")

    if gate_name == "trade" and "profit" in text.lower():
        errors.append(f"{prefix}: trade gate must not encode directional alpha")

    trivial_patterns = ("mention", "contains the word", "includes the phrase")
    lower = text.lower()
    if any(pat in lower for pat in trivial_patterns):
        errors.append(f"{prefix}: trivial always-pass wording")

    return errors


def load_preregistration(hypothesis_id: str) -> dict[str, Any]:
    path = hypothesis_dir(hypothesis_id) / "preregistration.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing preregistration: {path}")
    return load_json(path)


def compute_freeze_hashes(hypothesis_id: str) -> dict[str, str]:
    hdir = hypothesis_dir(hypothesis_id)
    hyp_path = hdir / "HYPOTHESIS.md"
    prereg_path = hdir / "preregistration.json"
    freeze_path = hdir / "freeze_manifest.json"
    if not all(p.is_file() for p in (hyp_path, prereg_path, freeze_path)):
        raise FileNotFoundError("hypothesis freeze artifacts incomplete")

    prereg = load_json(prereg_path)
    freeze = load_json(freeze_path)
    manifest_rel = freeze.get("artifacts", {}).get("data_manifest", {}).get("path")
    if not manifest_rel:
        raise ValueError("freeze_manifest missing data_manifest.path")

    from week_trader.util import repo_root

    manifest_path = Path(manifest_rel)
    if not manifest_path.is_absolute():
        manifest_path = repo_root() / manifest_path

    return {
        "HYPOTHESIS.md": sha256_file(hyp_path),
        "preregistration.json": sha256_file(prereg_path),
        "data_manifest": sha256_file(manifest_path),
        "data_manifest_id": str(prereg.get("data_manifest_id", "")),
    }
