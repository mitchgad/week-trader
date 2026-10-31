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
