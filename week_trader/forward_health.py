from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Literal

from week_trader.forward_track_record import ACTIVE_FORWARD_HYPOTHESIS_IDS
from week_trader.paper_forward import forward_dir, manifest_bar_interval
from week_trader.signal_intent import signal_is_flat
from week_trader.util import load_json, repo_root

Severity = Literal["ok", "warn", "critical"]

STALE_STATUS_HOURS_4H = 5.0
STALE_STATUS_HOURS_1D = 30.0
STALE_EVENTS_HOURS_4H = 5.0
STALE_EVENTS_HOURS_1D = 30.0

WORKFLOW_LOOKBACK_4H = 6.0
WORKFLOW_LOOKBACK_1D_WEEKDAY = 36.0
WORKFLOW_LOOKBACK_1D_WEEKEND = 72.0

ALPACA_PAPER_SECRETS = ("ALPACA_PAPER_KEY", "ALPACA_PAPER_SECRET")
ISSUE_43_URL = "https://github.com/mitchgad/week-trader/issues/43"


def hypothesis_workflow_filename(hypothesis_id: str) -> str:
    if hypothesis_id == "btc-spot-tsmom-4h":
        return "paper-forward-schedule.yml"
    return f"paper-forward-{hypothesis_id}.yml"


def stale_status_hours(hypothesis_id: str) -> float:
    try:
        interval = manifest_bar_interval(hypothesis_id)
    except Exception:
        return STALE_STATUS_HOURS_1D
    return STALE_STATUS_HOURS_4H if interval == "4h" else STALE_STATUS_HOURS_1D


def stale_events_hours(hypothesis_id: str) -> float:
    return stale_status_hours(hypothesis_id)


def workflow_lookback_hours(hypothesis_id: str, *, now: datetime | None = None) -> float:
    ref = now or datetime.now(UTC)
    try:
        interval = manifest_bar_interval(hypothesis_id)
    except Exception:
        interval = "1Day"
    if interval == "4h":
        return WORKFLOW_LOOKBACK_4H
    if ref.weekday() >= 5 or ref.weekday() == 0:
        return WORKFLOW_LOOKBACK_1D_WEEKEND
    return WORKFLOW_LOOKBACK_1D_WEEKDAY


def run_paper_forward_health_check(
    *,
    hypothesis_ids: tuple[str, ...] | None = None,
    now: datetime | None = None,
    github_fetch: Callable[[str], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """Aggregate scheduled health findings for the forward-paper fleet."""
    ref = now or datetime.now(UTC)
    ids = hypothesis_ids or ACTIVE_FORWARD_HYPOTHESIS_IDS
    findings: list[dict[str, Any]] = []

    findings.extend(check_github_actions_secrets())

    fetcher = github_fetch or _github_api_get
    if fetcher is not _github_api_get or _github_token():
        findings.extend(check_forward_workflow_runs(ids, now=ref, github_fetch=fetcher))
    else:
        findings.append(
            _finding(
                code="workflow_check_skipped",
                severity="warn",
                message="GITHUB_TOKEN unavailable — skipping paper-forward workflow run checks",
            )
        )

    for hypothesis_id in ids:
        findings.extend(check_forward_snapshot_staleness(hypothesis_id, now=ref))
        findings.extend(check_missing_wt_order(hypothesis_id, now=ref))

    severity = aggregate_severity(findings)
    report: dict[str, Any] = {
        "timestamp_utc": ref.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "severity": severity,
        "finding_count": len(findings),
        "findings": findings,
        "hypothesis_ids_checked": list(ids),
    }
    out_path = repo_root() / "paper" / "_shared" / "forward_health.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def check_github_actions_secrets() -> list[dict[str, Any]]:
    missing = [name for name in ALPACA_PAPER_SECRETS if not os.environ.get(name, "").strip()]
    if not missing:
        return []
    return [
        _finding(
            code="github_actions_secrets_missing",
            severity="critical",
            message=(
                "Required GitHub Actions secrets are not set in this environment: "
                f"{', '.join(missing)}. Issue #43 is still pending Mitch: "
                "ALPACA_PAPER_KEY and ALPACA_PAPER_SECRET are not set in repo Actions secrets. "
                f"See {ISSUE_43_URL}"
            ),
            missing_secret_names=missing,
            issue_43_pending=True,
        )
    ]


def check_forward_workflow_runs(
    hypothesis_ids: tuple[str, ...],
    *,
    now: datetime,
    github_fetch: Callable[[str], dict[str, Any] | None],
) -> list[dict[str, Any]]:
    workflows = _load_workflow_index(github_fetch)
    if workflows is None:
        return [
            _finding(
                code="workflow_index_unavailable",
                severity="warn",
                message="Could not load GitHub Actions workflow list — paper loop run state unknown",
            )
        ]

    findings: list[dict[str, Any]] = []
    for hypothesis_id in hypothesis_ids:
        workflow_file = hypothesis_workflow_filename(hypothesis_id)
        workflow_id = workflows.get(workflow_file)
        if workflow_id is None:
            findings.append(
                _finding(
                    code="workflow_not_found",
                    severity="critical",
                    hypothesis_id=hypothesis_id,
                    message=f"No GitHub Actions workflow file {workflow_file} for forward paper loop",
                    workflow_file=workflow_file,
                )
            )
            continue

        lookback = workflow_lookback_hours(hypothesis_id, now=now)
        runs_payload = github_fetch(
            f"/repos/{{repo}}/actions/workflows/{workflow_id}/runs?per_page=5&branch=main"
        )
        runs = _runs_list(runs_payload)
        if not runs:
            findings.append(
                _finding(
                    code="paper_loop_never_ran",
                    severity="critical",
                    hypothesis_id=hypothesis_id,
                    message=(
                        f"Paper forward workflow {workflow_file} has no recorded runs on main "
                        f"(lookback {lookback}h)"
                    ),
                    workflow_file=workflow_file,
                    lookback_hours=lookback,
                )
            )
            continue

        latest = runs[0]
        latest_conclusion = str(latest.get("conclusion") or "")
        latest_status = str(latest.get("status") or "")

        recent_success: dict[str, Any] | None = None
        for run in runs:
            if str(run.get("conclusion") or "") != "success":
                continue
            updated_at = _parse_github_ts(str(run.get("updated_at") or ""))
            if updated_at is None:
                continue
            age_hours = _hours_between(updated_at, now)
            if age_hours <= lookback:
                recent_success = run
                break

        if recent_success is None:
            latest_updated = _parse_github_ts(str(latest.get("updated_at") or ""))
            latest_age = (
                _hours_between(latest_updated, now) if latest_updated is not None else None
            )
            if latest_conclusion in {"failure", "cancelled", "timed_out"}:
                findings.append(
                    _finding(
                        code="paper_loop_run_failed",
                        severity="critical",
                        hypothesis_id=hypothesis_id,
                        message=(
                            f"Latest paper forward workflow run failed ({workflow_file}): "
                            f"conclusion={latest_conclusion!r}"
                        ),
                        workflow_file=workflow_file,
                        run_id=latest.get("id"),
                        html_url=latest.get("html_url"),
                    )
                )
            elif latest_status != "completed" or latest_conclusion != "success":
                findings.append(
                    _finding(
                        code="paper_loop_run_incomplete",
                        severity="warn",
                        hypothesis_id=hypothesis_id,
                        message=(
                            f"Latest paper forward workflow run not successful yet ({workflow_file}): "
                            f"status={latest_status!r} conclusion={latest_conclusion!r}"
                        ),
                        workflow_file=workflow_file,
                        run_id=latest.get("id"),
                    )
                )
            findings.append(
                _finding(
                    code="paper_loop_not_recent",
                    severity="critical",
                    hypothesis_id=hypothesis_id,
                    message=(
                        f"No successful paper forward run within {lookback}h for {hypothesis_id}"
                        + (
                            f" (latest run {latest_age:.1f}h ago)"
                            if latest_age is not None
                            else ""
                        )
                    ),
                    workflow_file=workflow_file,
                    lookback_hours=lookback,
                )
            )

    return findings


def check_forward_snapshot_staleness(hypothesis_id: str, *, now: datetime) -> list[dict[str, Any]]:
    directory = forward_dir(hypothesis_id)
    status_path = directory / "status.json"
    events_path = directory / "events.jsonl"
    findings: list[dict[str, Any]] = []

    status_threshold = stale_status_hours(hypothesis_id)
    events_threshold = stale_events_hours(hypothesis_id)

    if not status_path.is_file():
        findings.append(
            _finding(
                code="forward_status_missing",
                severity="warn",
                hypothesis_id=hypothesis_id,
                message=(
                    f"paper/{hypothesis_id}/forward/status.json missing — "
                    "no local forward monitor snapshot to assess"
                ),
            )
        )
    else:
        ts_raw = _read_status_timestamp(status_path)
        age = _age_hours_from_iso(ts_raw, now) if ts_raw else None
        if age is None:
            findings.append(
                _finding(
                    code="forward_status_invalid",
                    severity="warn",
                    hypothesis_id=hypothesis_id,
                    message=f"status.json timestamp_utc missing or invalid for {hypothesis_id}",
                )
            )
        elif age > status_threshold:
            findings.append(
                _finding(
                    code="forward_status_stale",
                    severity="critical",
                    hypothesis_id=hypothesis_id,
                    message=(
                        f"Forward status.json stale for {hypothesis_id}: "
                        f"{age:.1f}h old (limit {status_threshold}h for cadence)"
                    ),
                    age_hours=age,
                    stale_limit_hours=status_threshold,
                )
            )

    if not events_path.is_file():
        findings.append(
            _finding(
                code="forward_events_missing",
                severity="warn",
                hypothesis_id=hypothesis_id,
                message=(
                    f"paper/{hypothesis_id}/forward/events.jsonl missing — "
                    "no forward event log snapshot"
                ),
            )
        )
    else:
        last_event_ts = _last_event_timestamp(events_path)
        age = _age_hours_from_iso(last_event_ts, now) if last_event_ts else None
        if age is None:
            file_age = _file_age_hours(events_path, now)
            if file_age > events_threshold:
                findings.append(
                    _finding(
                        code="forward_events_stale",
                        severity="critical",
                        hypothesis_id=hypothesis_id,
                        message=(
                            f"Forward events.jsonl stale for {hypothesis_id}: "
                            f"file {file_age:.1f}h old (limit {events_threshold}h)"
                        ),
                        age_hours=file_age,
                        stale_limit_hours=events_threshold,
                    )
                )
        elif age > events_threshold:
            findings.append(
                _finding(
                    code="forward_events_stale",
                    severity="critical",
                    hypothesis_id=hypothesis_id,
                    message=(
                        f"Forward events.jsonl stale for {hypothesis_id}: "
                        f"last event {age:.1f}h old (limit {events_threshold}h)"
                    ),
                    age_hours=age,
                    stale_limit_hours=events_threshold,
                )
            )

    return findings


def check_missing_wt_order(hypothesis_id: str, *, now: datetime) -> list[dict[str, Any]]:
    events_path = forward_dir(hypothesis_id) / "events.jsonl"
    if not events_path.is_file():
        return []

    signals = _load_signal_events(events_path)
    if not signals:
        return []

    latest = signals[-1]
    signal_payload = latest.get("payload")
    if not isinstance(signal_payload, dict) or signal_is_flat(signal_payload):
        return []

    signal_ts = str(latest.get("timestamp_utc") or "")
    if _has_order_submitted_after(events_path, after_ts=signal_ts):
        return []

    if not _trade_gate_passed_after(hypothesis_id, after_ts=signal_ts):
        return []

    fill_tag = f"wt-{hypothesis_id}"
    return [
        _finding(
            code="missing_wt_order",
            severity="critical",
            hypothesis_id=hypothesis_id,
            message=(
                f"Gate-passed submit expected a {fill_tag} paper order after non-flat signal "
                f"at {signal_ts}, but no order_submitted event was recorded "
                "(flat signals and trade-gate blocks are excluded)"
            ),
            signal_timestamp_utc=signal_ts,
            expected_fill_tag=fill_tag,
        )
    ]


def aggregate_severity(findings: list[dict[str, Any]]) -> Severity:
    if not findings:
        return "ok"
    if any(f.get("severity") == "critical" for f in findings):
        return "critical"
    return "warn"


def format_health_summary(report: dict[str, Any]) -> str:
    lines = [
        f"paper-forward health: severity={report.get('severity')} "
        f"findings={report.get('finding_count')}",
    ]
    findings = report.get("findings")
    if not isinstance(findings, list):
        return "\n".join(lines)
    for item in findings[:40]:
        if not isinstance(item, dict):
            continue
        hid = item.get("hypothesis_id")
        prefix = f"[{item.get('severity')}] {item.get('code')}"
        if isinstance(hid, str):
            prefix += f" ({hid})"
        lines.append(f"{prefix}: {item.get('message')}")
    if len(findings) > 40:
        lines.append(f"... and {len(findings) - 40} more findings")
    return "\n".join(lines)


def _finding(
    *,
    code: str,
    severity: Severity,
    message: str,
    hypothesis_id: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "message": message,
    }
    if hypothesis_id:
        out["hypothesis_id"] = hypothesis_id
    out.update(extra)
    return out


def _load_workflow_index(
    github_fetch: Callable[[str], dict[str, Any] | None],
) -> dict[str, int] | None:
    payload = github_fetch("/repos/{repo}/actions/workflows?per_page=100")
    if payload is None:
        return None
    workflows = payload.get("workflows")
    if not isinstance(workflows, list):
        return None
    index: dict[str, int] = {}
    for wf in workflows:
        if not isinstance(wf, dict):
            continue
        path = wf.get("path")
        wf_id = wf.get("id")
        if isinstance(path, str) and isinstance(wf_id, int):
            index[Path(path).name] = wf_id
    return index


def _runs_list(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if payload is None:
        return []
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        return []
    return [r for r in runs if isinstance(r, dict)]


def _github_token() -> str | None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and token.strip():
        return token.strip()
    return None


def _github_repo() -> str | None:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo and repo.strip():
        return repo.strip()
    return None


def _github_api_get(path_template: str) -> dict[str, Any] | None:
    token = _github_token()
    repo = _github_repo()
    if not token or not repo:
        return None
    path = path_template.replace("{repo}", repo)
    url = f"https://api.github.com{path}"
    try:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return None
    if isinstance(body, dict):
        return body
    return None


def _read_status_timestamp(status_path: Path) -> str | None:
    loaded = load_json(status_path)
    if not isinstance(loaded, dict):
        return None
    ts = loaded.get("timestamp_utc")
    return ts if isinstance(ts, str) else None


def _last_event_timestamp(events_path: Path) -> str | None:
    last: str | None = None
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = event.get("timestamp_utc")
        if isinstance(ts, str):
            last = ts
    return last


def _load_signal_events(events_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event_type") != "signal":
            continue
        out.append(event)
    return out


def _has_order_submitted_after(events_path: Path, *, after_ts: str) -> bool:
    after = _parse_github_ts(after_ts)
    if after is None:
        return False
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event_type") != "order_submitted":
            continue
        ts = _parse_github_ts(str(event.get("timestamp_utc") or ""))
        if ts is not None and ts >= after:
            return True
    return False


def _trade_gate_passed_after(hypothesis_id: str, *, after_ts: str) -> bool:
    after = _parse_github_ts(after_ts)
    if after is None:
        return False
    gates_dir = repo_root() / "gates" / hypothesis_id
    if not gates_dir.is_dir():
        return False
    for path in sorted(gates_dir.glob("jev-trade-*.json")):
        loaded = load_json(path)
        if not isinstance(loaded, dict):
            continue
        if loaded.get("pass") is not True:
            continue
        ts = _parse_github_ts(str(loaded.get("timestamp_utc") or ""))
        if ts is not None and ts >= after:
            return True
    return False


def _parse_github_ts(raw: str) -> datetime | None:
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _age_hours_from_iso(ts_raw: str, now: datetime) -> float | None:
    ts = _parse_github_ts(ts_raw)
    if ts is None:
        return None
    return _hours_between(ts, now)


def _hours_between(earlier: datetime, later: datetime) -> float:
    delta = later.astimezone(UTC) - earlier.astimezone(UTC)
    return delta.total_seconds() / 3600.0


def _file_age_hours(path: Path, now: datetime) -> float:
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return _hours_between(mtime, now)
