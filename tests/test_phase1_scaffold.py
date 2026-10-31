from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_gate4_blocked_v1() -> None:
    from week_trader.gate4 import assert_gate4_closed

    assert_gate4_closed()


def test_lint_template_questions() -> None:
    from week_trader.prereg import lint_jev_questions, load_preregistration

    errors = lint_jev_questions(load_preregistration("_template"))
    assert errors == []


def test_build_system_one_payload_matches_typesafe_schema() -> None:
    from week_trader.typesafe_client import build_system_one_payload

    questions = [
        {
            "id": "spec_falsifiable",
            "type": "noul",
            "text": "Is the spec falsifiable?",
            "state_keys": ["fields.a"],
        },
    ]
    payload = build_system_one_payload(
        model_id="jev-1.14.0",
        state={"fields": {"a": True}},
        questions=questions,
    )
    assert set(payload) == {"model", "state", "questions"}
    assert payload["model"] == "jev-1.14.0"
    assert isinstance(payload["questions"], dict)
    assert not isinstance(payload["questions"], list)
    assert "spec_falsifiable" in payload["questions"]


def test_call_system_one_posts_object_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    from week_trader import typesafe_client

    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {"answers": {"spec_falsifiable": {"type": "noul", "noul": 0.9}}}

    def fake_post(url: str, **kwargs: object) -> FakeResponse:
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return FakeResponse()

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key-not-real")
    monkeypatch.setattr(typesafe_client.requests, "post", fake_post)

    questions = [
        {
            "id": "spec_falsifiable",
            "type": "noul",
            "text": "Is the spec falsifiable?",
            "state_keys": ["fields.a"],
        },
    ]
    typesafe_client.call_system_one(
        model_id="jev-1.14.0",
        state={"fields": {"a": True}},
        questions=questions,
    )

    body = captured["json"]
    assert isinstance(body, dict)
    assert isinstance(body["questions"], dict)
    assert body["questions"]["spec_falsifiable"]["type"] == "noul"


def test_call_system_one_fail_closed_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from week_trader.typesafe_client import TypeSafeError, call_system_one

    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(TypeSafeError, match="TYPESAFE_API_KEY"):
        call_system_one(model_id="jev-1.14.0", state={}, questions=[])


def test_prereg_questions_to_api_dict_shape() -> None:
    from week_trader.typesafe_client import prereg_questions_to_api

    questions = [
        {
            "id": "spec_falsifiable",
            "type": "noul",
            "text": "Is the spec falsifiable?",
            "state_keys": ["fields.a"],
        },
        {
            "id": "operational_ok",
            "type": "choice",
            "choices": ["proceed", "block"],
            "text": "May code submit?",
            "state_keys": ["fields.b"],
        },
    ]
    api = prereg_questions_to_api(questions)
    assert isinstance(api, dict)
    assert set(api) == {"spec_falsifiable", "operational_ok"}
    assert api["spec_falsifiable"]["type"] == "noul"
    assert api["operational_ok"]["criteria"] == {"proceed": None, "block": None}


def test_jev_gate_fail_closed_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("GATE_LOG_HMAC_SECRET", "test-hmac-secret-for-ci-only")
    from week_trader.jev_gate import JevGateError, run_jev_gate

    with pytest.raises(JevGateError, match="TYPESAFE_API_KEY"):
        run_jev_gate("_template", "spec")


def test_gate_log_sign_and_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATE_LOG_HMAC_SECRET", "test-hmac-secret-for-ci-only")
    from week_trader.gate_log import verify_gate_log_file, write_gate_log

    log = write_gate_log(
        "_template",
        "trade",
        freeze_manifest_hash="abc",
        state_hash="def",
        request_hash="ghi",
        response_body_hash="jkl",
        model_id="jev-1.14.0",
        passed=False,
        threshold_compare={"pass": False},
        response_body={"answers": {}},
    )
    ok, reason = verify_gate_log_file(log)
    assert ok, reason


def test_paper_order_blocks_on_halt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATE_LOG_HMAC_SECRET", "test-hmac-secret-for-ci-only")
    from week_trader.gate_log import write_gate_log
    from week_trader.paper_order import PaperOrderError, paper_order
    from week_trader.util import repo_root

    halt = repo_root() / "paper" / "_template" / "HALT"
    halt.parent.mkdir(parents=True, exist_ok=True)
    halt.write_text("dry-run\n", encoding="utf-8")

    freeze_hash = json.loads(
        (repo_root() / "hypotheses" / "_template" / "freeze_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    from week_trader.util import sha256_json

    freeze_hash_val = sha256_json(freeze_hash)

    log = write_gate_log(
        "_template",
        "trade",
        freeze_manifest_hash=freeze_hash_val,
        state_hash="s",
        request_hash="r",
        response_body_hash="b",
        model_id="jev-1.14.0",
        passed=True,
        threshold_compare={"pass": True},
        response_body={"answers": {}},
    )

    with pytest.raises(PaperOrderError, match="HALT"):
        paper_order("intent-1", log)

    halt.unlink()


def test_verify_backtest_requires_costs_and_parity() -> None:
    from week_trader.verify_backtest import VerifyBacktestError, verify_backtest

    with pytest.raises(VerifyBacktestError, match="no backtests"):
        verify_backtest("_template")


def test_no_typesafe_outside_allowlist() -> None:
    allowed = {
        ROOT / "week_trader/typesafe_client.py",
        ROOT / "week_trader/jev_gate.py",
    }
    for path in list(ROOT.rglob("*.py")):
        if path.parts[-1] == "__pycache__":
            continue
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "api.typesafe.ai" in text or "call_system_one" in text:
            assert path.resolve() in {p.resolve() for p in allowed}
