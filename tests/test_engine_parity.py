from __future__ import annotations

import json
from pathlib import Path

import pytest

from week_trader.engines.golden_slice import primary_buy_hold_net_return
from week_trader.engines.parity import EngineParityError, materialize_parity_run, run_engine_parity
from week_trader.verify_backtest import verify_backtest


def test_primary_golden_slice_deterministic() -> None:
    result = primary_buy_hold_net_return(fee_bps_per_side=10, slippage_bps_per_side=5)
    assert result["engine"] == "primary_golden_slice"
    assert result["bars"] == 10.0
    assert result["net_return"] == pytest.approx(result["gross_return"] - 0.003, rel=0, abs=1e-9)


def test_engine_parity_pass_with_injected_jesse_metrics() -> None:
    primary = primary_buy_hold_net_return(fee_bps_per_side=10, slippage_bps_per_side=5)
    jesse_stub = {"engine": "stub", "net_return": primary["net_return"]}
    report = run_engine_parity("_template", jesse_metrics=jesse_stub)
    assert report["status"] == "pass"
    assert report["max_abs_delta"] == 0.0


def test_engine_parity_fail_on_delta() -> None:
    primary = primary_buy_hold_net_return(fee_bps_per_side=10, slippage_bps_per_side=5)
    jesse_stub = {"engine": "stub", "net_return": primary["net_return"] + 0.5}
    with pytest.raises(EngineParityError):
        run_engine_parity("_template", jesse_metrics=jesse_stub)


def test_materialize_run_satisfies_verify_backtest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _root() -> Path:
        return tmp_path

    for target in (
        "week_trader.util.repo_root",
        "week_trader.engines.parity.repo_root",
        "week_trader.verify_backtest.repo_root",
        "week_trader.manifest.repo_root",
    ):
        monkeypatch.setattr(target, _root)

    (tmp_path / "hypotheses" / "_template").mkdir(parents=True)
    repo = Path(__file__).resolve().parents[1]
    for name in ("HYPOTHESIS.md", "preregistration.json", "freeze_manifest.json"):
        src = repo / "hypotheses" / "_template" / name
        (tmp_path / "hypotheses" / "_template" / name).write_text(src.read_text(encoding="utf-8"))

    (tmp_path / "data" / "manifests").mkdir(parents=True)
    manifest_src = repo / "data" / "manifests" / "example-btc-spot.yaml"
    (tmp_path / "data" / "manifests" / "example-btc-spot.yaml").write_text(
        manifest_src.read_text(encoding="utf-8")
    )

    primary = primary_buy_hold_net_return(fee_bps_per_side=10, slippage_bps_per_side=5)
    jesse_stub = {"engine": "stub", "net_return": primary["net_return"]}
    run_dir = materialize_parity_run("_template", jesse_metrics=jesse_stub)
    assert (run_dir / "metrics.json").is_file()
    assert (run_dir / "engine_parity.json").is_file()
    parity = json.loads((run_dir / "engine_parity.json").read_text(encoding="utf-8"))
    assert parity["status"] == "pass"

    result = verify_backtest("_template")
    assert result["status"] == "verify_backtest_ok_scaffold"
