from __future__ import annotations

import json
from pathlib import Path

import pytest

from week_trader.ci_evidence import resolve_ci_pass_fields, write_local_ci_evidence_file
from week_trader.deduced_reason import build_deduced_reason
from week_trader.gate_record import (
    append_gate_record,
    read_gate_records,
    records_path,
    verify_record_hashes,
)
from week_trader.typesafe_client import build_system_one_payload
from week_trader.util import sha256_json


def test_gate_record_round_trip_hashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("week_trader.gate_record.repo_root", lambda: tmp_path)
    state = {
        "fields": {"data_fresh": True, "gate": "trade", "last_signal_side": "long"},
        "metrics": {},
        "_state_hash": "placeholder",
    }
    state["_state_hash"] = sha256_json({"fields": state["fields"], "metrics": state["metrics"]})
    questions = [
        {
            "id": "operational_ok",
            "type": "choice",
            "choices": ["proceed", "block"],
            "text": "May code submit?",
            "state_keys": ["fields.data_fresh"],
        }
    ]
    request_body = build_system_one_payload(
        model_id="jev-1.14.0",
        state=state,
        questions=questions,
    )
    request_hash = sha256_json(request_body)
    response = {
        "answers": {
            "operational_ok": {
                "type": "choice",
                "choice": "block",
                "probabilities": {"proceed": 0.2, "block": 0.8},
            }
        }
    }
    threshold_compare = {
        "gate": "trade",
        "pass": False,
        "comparisons": [
            {
                "question_id": "operational_ok",
                "type": "choice",
                "probability": 0.2,
                "min_required": 0.7,
                "pass": False,
            }
        ],
    }
    deduced = build_deduced_reason(
        gate="trade",
        prereg={"thresholds": {"trade_gate_min_probability": 0.7}},
        state=state,
        questions=questions,
        response=response,
        threshold_compare=threshold_compare,
    )
    assert deduced["label"] == "deduced"

    gate_log = tmp_path / "gates" / "btc-spot-tsmom-4h" / "jev-trade-test.json"
    gate_log.parent.mkdir(parents=True)

    append_gate_record(
        hypothesis_id="btc-spot-tsmom-4h",
        gate="trade",
        gate_log_path=gate_log,
        freeze_manifest_hash="abc",
        state=state,
        request_body=request_body,
        request_hash=request_hash,
        state_hash=str(state["_state_hash"]),
        response_body_hash=sha256_json(response),
        model_id="jev-1.14.0",
        passed=False,
        threshold_compare=threshold_compare,
        response_body=response,
        deduced_reason=deduced,
        deployed_git_sha="deadbeef",
        ci_evidence_meta={"source": "test"},
    )

    records = read_gate_records("btc-spot-tsmom-4h")
    assert len(records) == 1
    ok, reason = verify_record_hashes(records[0])
    assert ok, reason
    assert records[0]["request_hash"] == request_hash
    assert records[0]["state_hash"] == state["_state_hash"]


def test_gate_records_append_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("week_trader.gate_record.repo_root", lambda: tmp_path)
    path = records_path("btc-spot-tsmom-4h")
    path.parent.mkdir(parents=True)
    path.write_text('{"record_version":1,"first":true}\n', encoding="utf-8")

    state = {"fields": {"gate": "trade"}, "metrics": {}}
    state_hash = sha256_json({"fields": state["fields"], "metrics": state["metrics"]})
    request_body = {"model": "jev-1.14.0", "state": state, "questions": {}}
    request_hash = sha256_json(request_body)
    deduced = {"label": "deduced", "summary": "test"}

    append_gate_record(
        hypothesis_id="btc-spot-tsmom-4h",
        gate="trade",
        gate_log_path=tmp_path / "gates" / "btc-spot-tsmom-4h" / "log.json",
        freeze_manifest_hash="f",
        state=state,
        request_body=request_body,
        request_hash=request_hash,
        state_hash=state_hash,
        response_body_hash="r",
        model_id="jev-1.14.0",
        passed=False,
        threshold_compare={"pass": False, "comparisons": []},
        response_body={"answers": {}},
        deduced_reason=deduced,
        deployed_git_sha="sha",
        ci_evidence_meta={},
    )

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["first"] is True


def test_unknown_ci_evidence_not_coerced_to_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("week_trader.ci_evidence._repo_root", lambda: tmp_path)
    monkeypatch.delenv("WEEK_TRADER_IMPLEMENTATION_AUDIT_PASS", raising=False)
    monkeypatch.delenv("WEEK_TRADER_UNIT_TESTS_PASS", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    impl, unit, meta = resolve_ci_pass_fields("abc123")
    assert impl == "unknown"
    assert unit == "unknown"
    assert meta["source"] == "unresolved"
    assert impl is not True
    assert unit is not True

    write_local_ci_evidence_file(
        "abc123",
        implementation_audit_pass=True,
        unit_tests_pass=True,
        source="test",
    )
    impl2, unit2, meta2 = resolve_ci_pass_fields("abc123")
    assert impl2 is True
    assert unit2 is True
    assert meta2["source"] == "ci_evidence_file"


def test_deduced_reason_label_and_below_threshold_without_false_inputs() -> None:
    state = {
        "fields": {
            "data_fresh": True,
            "within_risk_bands": True,
            "halt_absent": True,
        },
        "metrics": {},
    }
    questions = [
        {
            "id": "operational_ok",
            "type": "choice",
            "choices": ["proceed", "block"],
            "text": "May code submit?",
            "state_keys": [
                "fields.data_fresh",
                "fields.within_risk_bands",
                "fields.halt_absent",
            ],
        }
    ]
    threshold_compare = {
        "pass": False,
        "comparisons": [
            {
                "question_id": "operational_ok",
                "pass": False,
                "probability": 0.26,
                "min_required": 0.7,
            }
        ],
    }
    deduced = build_deduced_reason(
        gate="trade",
        prereg={"thresholds": {"trade_gate_min_probability": 0.7}},
        state=state,
        questions=questions,
        response={"answers": {}},
        threshold_compare=threshold_compare,
    )
    assert deduced["label"] == "deduced"
    assert deduced["all_declared_inputs_in_band"] is True
    assert "below the preregistered threshold" in deduced["summary"]
    assert "invent" not in deduced["summary"].lower()


def test_build_jev_state_uses_unknown_without_ci_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("week_trader.jev_state.repo_root", lambda: tmp_path)
    monkeypatch.setattr("week_trader.ci_evidence._repo_root", lambda: tmp_path)
    monkeypatch.setenv("WEEK_TRADER_DEPLOYED_SHA", "nosuch")
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "hypotheses/btc-spot-tsmom-4h/preregistration.json",
        "hypotheses/btc-spot-tsmom-4h/freeze_manifest.json",
        "hypotheses/btc-spot-tsmom-4h/HYPOTHESIS.md",
        "data/manifests/btc-spot-tsmom-4h-alpaca.yaml",
        "risk_limits.json",
    ):
        src = repo / rel
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8"))

    from week_trader.jev_state import build_jev_state

    state = build_jev_state("btc-spot-tsmom-4h", gate="spec")
    assert state["fields"]["implementation_audit_pass"] == "unknown"
    assert state["fields"]["unit_tests_pass"] == "unknown"
    assert state["fields"]["implementation_audit_pass"] is not True
