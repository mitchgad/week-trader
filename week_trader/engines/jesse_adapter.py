from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from week_trader.engines.golden_slice import GoldenSliceError, load_golden_closes


class JesseAdapterError(Exception):
    pass


def _fee_rate_from_bps(fee_bps_per_side: float) -> float:
    return fee_bps_per_side / 10_000.0


def _jesse_python() -> str:
    return os.environ.get("JESSE_PYTHON", sys.executable)


def _run_via_subprocess(closes: list[float], fee_bps_per_side: float) -> dict[str, object]:
    payload = {
        "closes": closes,
        "fee_rate": _fee_rate_from_bps(fee_bps_per_side),
        "starting_balance": 10_000,
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(payload, tmp)
        payload_path = tmp.name
    try:
        proc = subprocess.run(
            [
                _jesse_python(),
                "-m",
                "week_trader.jesse_isolated_runner",
                payload_path,
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(Path(__file__).resolve().parents[2]),
        )
    finally:
        Path(payload_path).unlink(missing_ok=True)

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise JesseAdapterError(
            "Jesse isolated backtest failed. Install Jesse in JESSE_PYTHON venv "
            "(MIT PyPI package; conflicts with main pandas pin). "
            f"Detail: {detail[:500]}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise JesseAdapterError(f"invalid Jesse runner output: {exc}") from exc


def _run_inprocess(closes: list[float], fee_bps_per_side: float) -> dict[str, object]:
    from week_trader.jesse_isolated_runner import run_from_payload

    payload = {
        "closes": closes,
        "fee_rate": _fee_rate_from_bps(fee_bps_per_side),
        "starting_balance": 10_000,
    }
    return run_from_payload(payload)


def jesse_golden_slice_net_return(
    *,
    fee_bps_per_side: float,
    slippage_bps_per_side: float = 0.0,
) -> dict[str, object]:
    """
    Thin wrapper around `jesse.research.backtest` (isolated API).
    Does not vendor the jesse-ai monorepo or embed freqtrade/Lean.
    """
    try:
        closes = load_golden_closes()
    except GoldenSliceError as exc:
        raise JesseAdapterError(str(exc)) from exc

    effective_fee_bps = fee_bps_per_side + slippage_bps_per_side
    try:
        import jesse  # noqa: F401

        return _run_inprocess(closes, effective_fee_bps)
    except ImportError:
        return _run_via_subprocess(closes, effective_fee_bps)
