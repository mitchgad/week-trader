from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from week_trader.jev_state import build_jev_state
from week_trader.paper_forward_order import resolve_order_intent_for_signal
from week_trader.util import load_json


def _write_signal_event(events_path: Path, payload: dict[str, object]) -> None:
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.write_text(
        json.dumps({"event_type": "signal", "payload": payload}) + "\n",
        encoding="utf-8",
    )


def _seed_trade_state_fixtures(tmp_path: Path, hypothesis_id: str) -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        f"hypotheses/{hypothesis_id}/preregistration.json",
        f"hypotheses/{hypothesis_id}/freeze_manifest.json",
        f"hypotheses/{hypothesis_id}/HYPOTHESIS.md",
        "risk_limits.json",
    ):
        src = repo / rel
        if not src.is_file():
            continue
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dest)
    manifest = repo / "data" / "manifests"
    if manifest.is_dir():
        dest_manifests = tmp_path / "data" / "manifests"
        dest_manifests.mkdir(parents=True, exist_ok=True)
        for path in manifest.glob(f"{hypothesis_id}*.yaml"):
            shutil.copy(path, dest_manifests / path.name)
    src_intents = repo / "paper" / hypothesis_id / "intents"
    if src_intents.is_dir():
        dest_intents = tmp_path / "paper" / hypothesis_id / "intents"
        dest_intents.mkdir(parents=True, exist_ok=True)
        for path in src_intents.glob("*.json"):
            shutil.copy(path, dest_intents / path.name)


@pytest.fixture
def jev_repo_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    for target in (
        "week_trader.util.repo_root",
        "week_trader.jev_state.repo_root",
        "week_trader.paper_forward.repo_root",
        "week_trader.manifest.repo_root",
        "week_trader.paper_forward_order.repo_root",
    ):
        monkeypatch.setattr(target, lambda: tmp_path)
    return tmp_path


def test_trade_gate_selects_xlf_not_first_eem_intent(jev_repo_root: Path) -> None:
    hid = "eem-xlf-csmom-1d"
    _seed_trade_state_fixtures(jev_repo_root, hid)
    signal = {"side": "long", "target_symbol": "XLF", "strategy": hid}
    _write_signal_event(
        jev_repo_root / "paper" / hid / "forward" / "events.jsonl",
        signal,
    )
    fields = build_jev_state(hid, gate="trade")["fields"]
    assert fields["order_intent_present"] is True
    assert fields["signal_matches_intent"] is True
    assert fields["order_intent_id"] == "market-long-xlf"
    assert fields["order_intent_symbol"] == "XLF"
    assert resolve_order_intent_for_signal(hid, signal) == (
        "market-long-xlf",
        load_json(jev_repo_root / "paper" / hid / "intents" / "market-long-xlf.json"),
    )


def test_trade_gate_mismatching_signal_yields_no_intent(jev_repo_root: Path) -> None:
    hid = "eem-xlf-csmom-1d"
    _seed_trade_state_fixtures(jev_repo_root, hid)
    _write_signal_event(
        jev_repo_root / "paper" / hid / "forward" / "events.jsonl",
        {"side": "long", "target_symbol": "XLF", "strategy": hid},
    )
    (jev_repo_root / "paper" / hid / "intents" / "market-long-xlf.json").unlink()
    fields = build_jev_state(hid, gate="trade")["fields"]
    assert fields["order_intent_present"] is False
    assert fields["signal_matches_intent"] is False
    assert fields["order_intent_symbol"] is None


def test_trade_gate_crypto_alts_picks_signaled_winner_leg(jev_repo_root: Path) -> None:
    hid = "crypto-alts-csmom-4h"
    _seed_trade_state_fixtures(jev_repo_root, hid)
    _write_signal_event(
        jev_repo_root / "paper" / hid / "forward" / "events.jsonl",
        {"side": "long", "target_symbol": "LTCUSD", "strategy": hid},
    )
    fields = build_jev_state(hid, gate="trade")["fields"]
    assert fields["order_intent_id"] == "market-long-ltcusd"
    assert fields["order_intent_symbol"] == "LTCUSD"
    assert fields["signal_matches_intent"] is True
    first_intent = sorted(
        (jev_repo_root / "paper" / hid / "intents").glob("*.json")
    )[0].stem
    assert first_intent == "market-long-avaxusd"
    assert fields["order_intent_id"] != first_intent


def test_trade_gate_vb_vv_pairs_matching_leg_not_unrelated_first(jev_repo_root: Path) -> None:
    hid = "vb-vv-size-spread-1d"
    _seed_trade_state_fixtures(jev_repo_root, hid)
    signal = {"side": "pairs", "long_symbol": "VB", "short_symbol": "VV", "strategy": hid}
    _write_signal_event(
        jev_repo_root / "paper" / hid / "forward" / "events.jsonl",
        signal,
    )
    fields = build_jev_state(hid, gate="trade")["fields"]
    assert fields["order_intent_present"] is True
    assert fields["signal_matches_intent"] is True
    resolved = resolve_order_intent_for_signal(hid, signal)
    assert resolved is not None
    assert fields["order_intent_id"] == resolved[0]
    assert fields["order_intent_id"] == "market-long-vb"
    assert fields["order_intent_symbol"] == "VB"
