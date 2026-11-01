from __future__ import annotations

import json
from pathlib import Path

import pytest

from week_trader.forward_track_record import (
    RUNNING_STRATEGY_COUNT,
    build_forward_evidence_check,
    build_strategy_attribution,
    deflated_sharpe_threshold,
    min_track_record_length,
    probabilistic_sharpe_ratio,
)


def test_probabilistic_sharpe_high_when_sample_beats_benchmark() -> None:
    psr = probabilistic_sharpe_ratio(
        0.5,
        0.0,
        observation_count=200,
        skewness=0.0,
        kurtosis=3.0,
    )
    assert psr > 0.99


def test_probabilistic_sharpe_low_when_sample_below_benchmark() -> None:
    psr = probabilistic_sharpe_ratio(
        -0.35,
        0.0,
        observation_count=80,
        skewness=0.0,
        kurtosis=3.0,
    )
    assert psr < 0.05


def test_min_trl_grows_when_sharpe_near_benchmark() -> None:
    low_edge = min_track_record_length(0.05, 0.0, skewness=0.0, kurtosis=3.0)
    high_edge = min_track_record_length(0.4, 0.0, skewness=0.0, kurtosis=3.0)
    assert high_edge < low_edge


def test_deflated_sharpe_threshold_rises_with_running_strategies() -> None:
    small = deflated_sharpe_threshold(running_strategies=2, observation_count=100)
    large = deflated_sharpe_threshold(running_strategies=14, observation_count=100)
    assert large > small


def test_running_strategy_count_matches_readme_fleet() -> None:
    assert RUNNING_STRATEGY_COUNT == 14


def test_build_strategy_attribution_filters_manifest_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "week_trader.paper_forward.manifest_universe_symbols",
        lambda _hid: ["SPY"],
    )
    positions = [
        {"symbol": "SPY", "qty": "10", "market_value": "5000", "unrealized_pl": "12"},
        {"symbol": "QQQ", "qty": "5", "market_value": "2500", "unrealized_pl": "3"},
    ]
    attr = build_strategy_attribution("spy-equity-tsmom-1d", positions)
    assert attr["gross_market_value_usd"] == pytest.approx(5000.0)
    assert len(attr["positions"]) == 1


def test_forward_evidence_insufficient_data_without_snapshots(tmp_path: Path) -> None:
    forward = tmp_path / "forward"
    forward.mkdir()
    report = build_forward_evidence_check("spy-equity-tsmom-1d", forward_directory=forward)
    assert report["evidence_status"] == "insufficient_data"
    assert report["not_enough_data_yet"] is True
    assert (forward / "evidence.json").is_file()


def test_forward_evidence_pass_with_long_positive_track_monkeypatched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    forward = tmp_path / "forward"
    forward.mkdir()
    events = forward / "events.jsonl"
    lines = []
    for i in range(40):
        gross = 2000.0 + i * 40.0 + (i % 3) * 2.5
        payload = {"strategy_attribution": {"gross_market_value_usd": gross}}
        lines.append(
            json.dumps(
                {
                    "event_type": "pnl_snapshot",
                    "timestamp_utc": f"2026-09-{(i % 28) + 1:02d}T12:00:00Z",
                    "payload": payload,
                }
            )
        )
    events.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        "week_trader.forward_track_record._strategy_slice_notional",
        lambda _hid: 5000.0,
    )
    report = build_forward_evidence_check("spy-equity-tsmom-1d", forward_directory=forward)
    assert report["evidence_status"] == "pass"
    assert report["not_enough_data_yet"] is False


def test_forward_evidence_fail_on_sustained_losses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    forward = tmp_path / "forward"
    forward.mkdir()
    events = forward / "events.jsonl"
    lines = []
    for i in range(40):
        gross = 5000.0 - i * 30.0 - (i % 4) * 1.5
        payload = {"strategy_attribution": {"gross_market_value_usd": gross}}
        lines.append(
            json.dumps(
                {
                    "event_type": "pnl_snapshot",
                    "timestamp_utc": f"2026-08-{(i % 28) + 1:02d}T12:00:00Z",
                    "payload": payload,
                }
            )
        )
    events.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        "week_trader.forward_track_record._strategy_slice_notional",
        lambda _hid: 5000.0,
    )
    report = build_forward_evidence_check("spy-equity-tsmom-1d", forward_directory=forward)
    assert report["evidence_status"] == "fail"
    assert report["not_enough_data_yet"] is False
