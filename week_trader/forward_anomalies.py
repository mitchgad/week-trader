from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from week_trader.paper_forward import append_forward_event, forward_dir
from week_trader.util import load_json, repo_root

STALE_STATUS_HOURS = 5.0
EQUITY_DRAWDOWN_WARN_PCT = 5.0
PNL_SNAPSHOT_GAP_HOURS = 6.0


def check_forward_anomalies(hypothesis_id: str) -> dict[str, Any]:
    """
    Read forward status.json and events.jsonl; emit structured alerts (no orders).
    """
    root = repo_root()
    halt_path = root / "paper" / hypothesis_id / "HALT"
    directory = forward_dir(hypothesis_id)
    status_path = directory / "status.json"
    events_path = directory / "events.jsonl"

    alerts: list[dict[str, Any]] = []
    if halt_path.is_file():
        alerts.append(
            {
                "code": "halt_active",
                "severity": "critical",
                "message": "HALT file present — paper loop must not trade",
            }
        )

    status: dict[str, Any] | None = None
    if status_path.is_file():
        loaded = load_json(status_path)
        if isinstance(loaded, dict):
            status = loaded
        else:
            alerts.append(
                {
                    "code": "status_invalid",
                    "severity": "warn",
                    "message": "status.json is not an object",
                }
            )
    else:
        alerts.append(
            {
                "code": "status_missing",
                "severity": "warn",
                "message": "status.json missing — run paper-forward monitor",
            }
        )

    if status is not None:
        ts_raw = status.get("timestamp_utc")
        if isinstance(ts_raw, str):
            age_hours = _age_hours(ts_raw)
            if age_hours is not None and age_hours > STALE_STATUS_HOURS:
                alerts.append(
                    {
                        "code": "stale_status",
                        "severity": "warn",
                        "message": f"status.json older than {STALE_STATUS_HOURS}h",
                        "age_hours": age_hours,
                    }
                )
        equity = _float_or_none(status.get("account_equity"))
        if equity is not None and equity <= 0:
            alerts.append(
                {
                    "code": "non_positive_equity",
                    "severity": "critical",
                    "message": "account_equity non-positive in status snapshot",
                    "equity": equity,
                }
            )

    snapshots = _recent_pnl_snapshots(events_path, limit=2)
    if len(snapshots) >= 2:
        prev_eq = _float_or_none(snapshots[-2].get("equity"))
        curr_eq = _float_or_none(snapshots[-1].get("equity"))
        if prev_eq and curr_eq and prev_eq > 0:
            drop_pct = (prev_eq - curr_eq) / prev_eq * 100.0
            if drop_pct >= EQUITY_DRAWDOWN_WARN_PCT:
                alerts.append(
                    {
                        "code": "equity_drawdown",
                        "severity": "warn",
                        "message": f"equity dropped {drop_pct:.2f}% vs prior pnl_snapshot",
                        "drop_pct": drop_pct,
                    }
                )

    last_pnl_ts = _last_event_timestamp(events_path, "pnl_snapshot")
    if last_pnl_ts is None and events_path.is_file():
        alerts.append(
            {
                "code": "no_pnl_snapshots",
                "severity": "warn",
                "message": "events.jsonl has no pnl_snapshot events",
            }
        )
    elif last_pnl_ts is not None:
        gap = _age_hours(last_pnl_ts)
        if gap is not None and gap > PNL_SNAPSHOT_GAP_HOURS:
            alerts.append(
                {
                    "code": "pnl_snapshot_gap",
                    "severity": "warn",
                    "message": f"no recent pnl_snapshot within {PNL_SNAPSHOT_GAP_HOURS}h",
                    "hours_since_last": gap,
                }
            )

    severity = _aggregate_severity(alerts)
    report = {
        "hypothesis_id": hypothesis_id,
        "timestamp_utc": _utc_now(),
        "severity": severity,
        "alert_count": len(alerts),
        "alerts": alerts,
    }
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "alerts.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    append_forward_event(hypothesis_id, "anomaly_check", report)
    return report


def _aggregate_severity(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return "ok"
    if any(a.get("severity") == "critical" for a in alerts):
        return "critical"
    return "warn"


def _recent_pnl_snapshots(events_path: Path, limit: int) -> list[dict[str, Any]]:
    if not events_path.is_file():
        return []
    snapshots: list[dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event_type") != "pnl_snapshot":
            continue
        payload = event.get("payload")
        if isinstance(payload, dict):
            snapshots.append(payload)
    return snapshots[-limit:]


def _last_event_timestamp(events_path: Path, event_type: str) -> str | None:
    if not events_path.is_file():
        return None
    last: str | None = None
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event_type") == event_type:
            ts = event.get("timestamp_utc")
            if isinstance(ts, str):
                last = ts
    return last


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


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
