from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from week_trader.forward_health import (
    aggregate_severity,
    check_forward_snapshot_staleness,
    check_github_actions_secrets,
    check_missing_wt_order,
    format_health_summary,
    hypothesis_workflow_filename,
    run_paper_forward_health_check,
    stale_status_hours,
    workflow_lookback_hours,
)


def test_hypothesis_workflow_filename_btc_uses_schedule() -> None:
    assert hypothesis_workflow_filename("btc-spot-tsmom-4h") == "paper-forward-schedule.yml"
    assert hypothesis_workflow_filename("spy-equity-tsmom-1d") == "paper-forward-spy-equity-tsmom-1d.yml"


def test_stale_hours_match_cadence() -> None:
    assert stale_status_hours("btc-spot-tsmom-4h") == 5.0
    assert stale_status_hours("spy-equity-tsmom-1d") == 30.0


def test_workflow_lookback_weekend_wider_for_equity() -> None:
    monday = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
    saturday = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    assert workflow_lookback_hours("spy-equity-tsmom-1d", now=monday) == 72.0
    assert workflow_lookback_hours("spy-equity-tsmom-1d", now=saturday) == 72.0
    assert workflow_lookback_hours("btc-spot-tsmom-4h", now=saturday) == 6.0


def test_check_github_actions_secrets_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPACA_PAPER_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_SECRET", raising=False)
    findings = check_github_actions_secrets()
    assert len(findings) == 1
    assert findings[0]["code"] == "github_actions_secrets_missing"
    assert findings[0]["severity"] == "critical"
    assert "Issue #43 is still pending Mitch" in findings[0]["message"]
    assert findings[0]["issue_43_pending"] is True


def test_check_github_actions_secrets_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_KEY", "present")
    monkeypatch.setenv("ALPACA_PAPER_SECRET", "present")
    assert check_github_actions_secrets() == []


def test_stale_status_critical(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("week_trader.forward_health.repo_root", lambda: tmp_path)
    monkeypatch.setattr("week_trader.paper_forward.repo_root", lambda: tmp_path)
    hid = "btc-spot-tsmom-4h"
    forward = tmp_path / "paper" / hid / "forward"
    forward.mkdir(parents=True)
    (forward / "status.json").write_text(
        json.dumps({"timestamp_utc": "2020-01-01T00:00:00Z"}) + "\n",
        encoding="utf-8",
    )
    (forward / "events.jsonl").write_text(
        json.dumps({"timestamp_utc": "2026-11-02T00:00:00Z", "event_type": "pnl_snapshot"})
        + "\n",
        encoding="utf-8",
    )
    now = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
    findings = check_forward_snapshot_staleness(hid, now=now)
    codes = {f["code"] for f in findings}
    assert "forward_status_stale" in codes


def test_missing_wt_order_after_gate_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("week_trader.forward_health.repo_root", lambda: tmp_path)
    monkeypatch.setattr("week_trader.paper_forward.repo_root", lambda: tmp_path)
    hid = "btc-spot-tsmom-4h"
    forward = tmp_path / "paper" / hid / "forward"
    forward.mkdir(parents=True)
    gates = tmp_path / "gates" / hid
    gates.mkdir(parents=True)
    (gates / "jev-trade-2026-11-02T010000Z.json").write_text(
        json.dumps(
            {
                "pass": True,
                "timestamp_utc": "2026-11-02T01:00:00Z",
                "gate": "trade",
                "hypothesis_id": hid,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    events = forward / "events.jsonl"
    events.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_type": "signal",
                        "timestamp_utc": "2026-11-02T00:30:00Z",
                        "payload": {"side": "long"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    findings = check_missing_wt_order(hid, now=datetime(2026, 11, 2, 12, 0, tzinfo=UTC))
    assert len(findings) == 1
    assert findings[0]["code"] == "missing_wt_order"


def test_missing_wt_order_skips_flat_signal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("week_trader.forward_health.repo_root", lambda: tmp_path)
    monkeypatch.setattr("week_trader.paper_forward.repo_root", lambda: tmp_path)
    hid = "btc-spot-tsmom-4h"
    forward = tmp_path / "paper" / hid / "forward"
    forward.mkdir(parents=True)
    (forward / "events.jsonl").write_text(
        json.dumps(
            {
                "event_type": "signal",
                "timestamp_utc": "2026-11-02T00:30:00Z",
                "payload": {"side": "flat"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert check_missing_wt_order(hid, now=datetime(2026, 11, 2, 12, 0, tzinfo=UTC)) == []


def test_workflow_run_failed_finding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("week_trader.forward_health.repo_root", lambda: tmp_path)
    monkeypatch.setenv("ALPACA_PAPER_KEY", "k")
    monkeypatch.setenv("ALPACA_PAPER_SECRET", "s")

    def fake_fetch(path: str) -> dict[str, object] | None:
        if path.endswith("/actions/workflows?per_page=100"):
            return {
                "workflows": [
                    {"path": ".github/workflows/paper-forward-schedule.yml", "id": 99},
                ]
            }
        if "/actions/workflows/99/runs" in path:
            return {
                "workflow_runs": [
                    {
                        "conclusion": "failure",
                        "status": "completed",
                        "updated_at": "2026-11-02T10:00:00Z",
                        "id": 1,
                        "html_url": "https://example.com/run/1",
                    }
                ]
            }
        return None

    report = run_paper_forward_health_check(
        hypothesis_ids=("btc-spot-tsmom-4h",),
        now=datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
        github_fetch=fake_fetch,
    )
    codes = {f["code"] for f in report["findings"]}
    assert "paper_loop_run_failed" in codes
    assert "paper_loop_not_recent" in codes
    assert report["severity"] == "critical"


def test_format_health_summary_includes_messages() -> None:
    report = {
        "severity": "critical",
        "finding_count": 1,
        "findings": [
            {
                "code": "github_actions_secrets_missing",
                "severity": "critical",
                "message": "Issue #43 is still pending Mitch",
            }
        ],
    }
    text = format_health_summary(report)
    assert "paper-forward health" in text
    assert "Issue #43" in text


def test_aggregate_severity() -> None:
    assert aggregate_severity([]) == "ok"
    assert aggregate_severity([{"severity": "warn"}]) == "warn"
    assert aggregate_severity([{"severity": "warn"}, {"severity": "critical"}]) == "critical"
