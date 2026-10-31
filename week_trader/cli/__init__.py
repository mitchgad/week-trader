from __future__ import annotations

import sys
from pathlib import Path

from week_trader.gate_log import verify_gate_log_file
from week_trader.jev_gate import JevGateError, run_jev_gate
from week_trader.jev_state import write_state_artifact
from week_trader.manifest import validate_manifest_file
from week_trader.paper_order import PaperOrderError, paper_order
from week_trader.prereg import lint_jev_questions as lint_jev_questions_for_prereg
from week_trader.prereg import load_preregistration
from week_trader.gate4 import assert_gate4_closed
from week_trader.verify_backtest import VerifyBacktestError
from week_trader.verify_backtest import verify_backtest as run_verify_backtest
from week_trader.engines.parity import EngineParityError, materialize_parity_run, run_engine_parity
from week_trader.util import hypothesis_dir, repo_root


def _exit_fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def main_jev_gate(argv: list[str] | None = None) -> None:
    args = argv or sys.argv[1:]
    hypothesis_id = _arg_value(args, "ID")
    gate = _arg_value(args, "GATE")
    metrics = _optional_path(args, "METRICS")
    try:
        path = run_jev_gate(hypothesis_id, gate, metrics_path=metrics)
    except JevGateError as exc:
        _exit_fail(str(exc))
    print(path)


def main_build_state(argv: list[str] | None = None) -> None:
    args = argv or sys.argv[1:]
    hypothesis_id = _arg_value(args, "ID")
    gate = _arg_value(args, "GATE")
    out = repo_root() / "internal" / "jev-state" / f"{hypothesis_id}-{gate}.json"
    metrics = _optional_path(args, "METRICS")
    write_state_artifact(hypothesis_id, gate, out, metrics)
    print(out)


def main_verify_gate_log(argv: list[str] | None = None) -> None:
    args = argv or sys.argv[1:]
    if not args:
        _exit_fail("usage: verify-gate-log <path>")
    path = Path(args[0])
    if not path.is_absolute():
        path = repo_root() / path
    ok, reason = verify_gate_log_file(path)
    if not ok:
        _exit_fail(reason)
    print("ok")


def main_lint_jev_questions(argv: list[str] | None = None) -> None:
    args = argv or sys.argv[1:]
    hypothesis_id = _arg_value(args, "ID")
    prereg = load_preregistration(hypothesis_id)
    errors = lint_jev_questions_for_prereg(prereg)
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        raise SystemExit(1)
    print("ok")


def main_paper_order(argv: list[str] | None = None) -> None:
    args = argv or sys.argv[1:]
    intent = _arg_value(args, "INTENT")
    gate_log = Path(_arg_value(args, "GATE_LOG"))
    if not gate_log.is_absolute():
        gate_log = repo_root() / gate_log
    try:
        result = paper_order(intent, gate_log)
    except PaperOrderError as exc:
        _exit_fail(str(exc))
    print(result)


def main_verify_backtest(argv: list[str] | None = None) -> None:
    args = argv or sys.argv[1:]
    hypothesis_id = _arg_value(args, "ID")
    try:
        result = run_verify_backtest(hypothesis_id)
    except VerifyBacktestError as exc:
        _exit_fail(str(exc))
    print(result)


def main_engine_parity(argv: list[str] | None = None) -> None:
    args = argv or sys.argv[1:]
    hypothesis_id = _arg_value(args, "ID")
    write_run = any(arg in ("--write-run",) for arg in args)
    try:
        if write_run:
            run_dir = materialize_parity_run(hypothesis_id)
            print(run_dir)
        else:
            print(run_engine_parity(hypothesis_id))
    except EngineParityError as exc:
        _exit_fail(str(exc))


def main_data_validate(argv: list[str] | None = None) -> None:
    args = argv or sys.argv[1:]
    manifest = repo_root() / "data" / "manifests" / "example-btc-spot.yaml"
    if args:
        manifest = Path(args[0])
        if not manifest.is_absolute():
            manifest = repo_root() / manifest
    errors = validate_manifest_file(manifest)
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        raise SystemExit(1)
    print("ok")


def main_gate4_closed(argv: list[str] | None = None) -> None:
    try:
        assert_gate4_closed()
    except Exception as exc:
        _exit_fail(str(exc))
    print("gate4 closed")


def _arg_value(args: list[str], key: str) -> str:
    prefix = f"{key}="
    for arg in args:
        if arg.startswith(prefix):
            return arg.split("=", 1)[1]
    _exit_fail(f"missing {prefix}<value>")
    raise AssertionError


def _optional_path(args: list[str], key: str) -> Path | None:
    prefix = f"{key}="
    for arg in args:
        if arg.startswith(prefix):
            raw = arg.split("=", 1)[1]
            path = Path(raw)
            if not path.is_absolute():
                path = repo_root() / path
            return path
    return None
