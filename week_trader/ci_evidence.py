from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from typing import Any, Literal

PassValue = bool | Literal["unknown"]


class CiEvidenceError(Exception):
    pass


def deployed_git_sha() -> str:
    """Git SHA of the code actually running (deployed commit)."""
    for key in ("WEEK_TRADER_DEPLOYED_SHA", "GITHUB_SHA"):
        raw = os.environ.get(key)
        if raw and raw.strip():
            return raw.strip()
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_repo_root(),
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
    return out.strip()


def resolve_ci_pass_fields(deployed_sha: str) -> tuple[PassValue, PassValue, dict[str, Any]]:
    """
    implementation_audit_pass: repo CI scaffold checks (non-pytest) for deployed_sha.
    unit_tests_pass: pytest step on CI for deployed_sha.
    Never returns True without recorded evidence.
    """
    meta: dict[str, Any] = {"deployed_sha": deployed_sha, "source": None}

    if deployed_sha in ("", "unknown"):
        meta["source"] = "missing_deployed_sha"
        return "unknown", "unknown", meta

    file_evidence = _load_evidence_file(deployed_sha)
    if file_evidence is not None:
        meta["source"] = "ci_evidence_file"
        meta["path"] = file_evidence.get("_path")
        return (
            _coerce_pass(file_evidence.get("implementation_audit_pass"), meta, "implementation_audit"),
            _coerce_pass(file_evidence.get("unit_tests_pass"), meta, "unit_tests"),
            meta,
        )

    env_impl = os.environ.get("WEEK_TRADER_IMPLEMENTATION_AUDIT_PASS")
    env_unit = os.environ.get("WEEK_TRADER_UNIT_TESTS_PASS")
    if env_impl is not None or env_unit is not None:
        meta["source"] = "environment"
        return (
            _coerce_pass(env_impl, meta, "implementation_audit"),
            _coerce_pass(env_unit, meta, "unit_tests"),
            meta,
        )

    github = _github_ci_evidence(deployed_sha)
    if github is not None:
        meta["source"] = "github_checks"
        meta.update(github.get("meta", {}))
        return (
            github.get("implementation_audit_pass", "unknown"),
            github.get("unit_tests_pass", "unknown"),
            meta,
        )

    meta["source"] = "unresolved"
    return "unknown", "unknown", meta


def _coerce_pass(raw: Any, meta: dict[str, Any], field: str) -> PassValue:
    if raw is True or raw is False:
        meta[field] = raw
        return raw
    if isinstance(raw, str):
        lowered = raw.strip().lower()
        if lowered == "true":
            meta[field] = True
            return True
        if lowered == "false":
            meta[field] = False
            return False
        if lowered == "unknown":
            meta[field] = "unknown"
            return "unknown"
    meta[field] = "unknown"
    return "unknown"


def _load_evidence_file(deployed_sha: str) -> dict[str, Any] | None:
    path = _repo_root() / ".ci-evidence" / f"{deployed_sha}.json"
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict):
        return None
    loaded["_path"] = str(path)
    return loaded


def _github_ci_evidence(deployed_sha: str) -> dict[str, Any] | None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return None

    url = f"https://api.github.com/repos/{repo}/commits/{deployed_sha}/check-runs?per_page=100"
    try:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return None

    runs = body.get("check_runs")
    if not isinstance(runs, list) or not runs:
        return None

    pytest_conclusions: list[str] = []
    audit_conclusions: list[str] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        name = str(run.get("name", ""))
        conclusion = run.get("conclusion")
        if not isinstance(conclusion, str):
            continue
        if name.lower() == "pytest" or "pytest" in name.lower():
            pytest_conclusions.append(conclusion)
        elif name == "ci" or name.startswith("scaffold") or "ci" in name.lower():
            audit_conclusions.append(conclusion)
        else:
            audit_conclusions.append(conclusion)

    def status_from(conclusions: list[str]) -> PassValue:
        if not conclusions:
            return "unknown"
        if any(c == "failure" or c == "cancelled" or c == "timed_out" for c in conclusions):
            return False
        if all(c == "success" for c in conclusions):
            return True
        if any(c == "success" for c in conclusions):
            return True
        return "unknown"

    unit = status_from(pytest_conclusions) if pytest_conclusions else status_from(
        [r.get("conclusion") for r in runs if isinstance(r, dict) and isinstance(r.get("conclusion"), str)]
    )
    audit = status_from(audit_conclusions) if audit_conclusions else unit

    return {
        "implementation_audit_pass": audit,
        "unit_tests_pass": unit,
        "meta": {
            "check_run_count": len(runs),
            "pytest_check_runs": len(pytest_conclusions),
        },
    }


def _repo_root() -> os.PathLike[str]:
    from week_trader.util import repo_root

    return repo_root()


def write_local_ci_evidence_file(
    deployed_sha: str,
    *,
    implementation_audit_pass: PassValue,
    unit_tests_pass: PassValue,
    source: str = "local_ci",
) -> None:
    """Test helper and CI step: persist evidence for a SHA (append-only per SHA file)."""
    root = _repo_root()
    out_dir = root / ".ci-evidence"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{deployed_sha}.json"
    if path.exists():
        return
    payload = {
        "deployed_sha": deployed_sha,
        "implementation_audit_pass": implementation_audit_pass,
        "unit_tests_pass": unit_tests_pass,
        "source": source,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
