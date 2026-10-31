from __future__ import annotations

import json
from pathlib import Path

import pytest

from week_trader.util import repo_root, sha256_json


def _write_template_intent(intent_id: str) -> None:
    intents_dir = repo_root() / "paper" / "_template" / "intents"
    intents_dir.mkdir(parents=True, exist_ok=True)
    path = intents_dir / f"{intent_id}.json"
    path.write_text(
        json.dumps(
            {
                "symbol": "BTCUSD",
                "side": "buy",
                "qty": "0.001",
                "type": "market",
                "time_in_force": "gtc",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _trade_gate_log(monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GATE_LOG_HMAC_SECRET", "test-hmac-secret-for-ci-only")
    from week_trader.gate_log import write_gate_log

    freeze_hash = sha256_json(
        json.loads(
            (repo_root() / "hypotheses" / "_template" / "freeze_manifest.json").read_text(
                encoding="utf-8"
            )
        )
    )
    return write_gate_log(
        "_template",
        "trade",
        freeze_manifest_hash=freeze_hash,
        state_hash="s",
        request_hash="r",
        response_body_hash="b",
        model_id="jev-1.14.0",
        passed=True,
        threshold_compare={"pass": True},
        response_body={"answers": {}},
    )


def test_require_paper_alpaca_host_refuses_non_paper() -> None:
    from week_trader.brokers.alpaca_paper import AlpacaPaperError, require_paper_alpaca_host

    with pytest.raises(AlpacaPaperError, match="refusing non-paper"):
        require_paper_alpaca_host("https://api.alpaca.markets")


def test_submit_fail_closed_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    from week_trader.brokers.alpaca_paper import AlpacaPaperError, submit_alpaca_paper_order

    monkeypatch.delenv("ALPACA_PAPER_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_SECRET", raising=False)
    with pytest.raises(AlpacaPaperError, match="ALPACA_PAPER_KEY"):
        submit_alpaca_paper_order(intent={"symbol": "BTCUSD", "side": "buy", "qty": "1"})


def test_paper_order_dry_run_zero_broker_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPACA_PAPER_KEY", raising=False)
    _write_template_intent("dry-run-intent")
    log = _trade_gate_log(monkeypatch)
    from week_trader.paper_order import paper_order

    result = paper_order("dry-run-intent", log, dry_run=True)
    assert result["broker_calls"] == 0
    assert result.get("dry_run") is True


def test_paper_order_submits_via_paper_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_KEY", "paper-key-test")
    monkeypatch.setenv("ALPACA_PAPER_SECRET", "paper-secret-test")
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets")
    _write_template_intent("submit-intent")
    log = _trade_gate_log(monkeypatch)

    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200
        content = b'{"id":"ord-123","status":"accepted","symbol":"BTCUSD"}'

        @staticmethod
        def json() -> dict[str, str]:
            return {"id": "ord-123", "status": "accepted", "symbol": "BTCUSD"}

    def fake_post(url: str, **kwargs: object) -> FakeResponse:
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        captured["json"] = kwargs.get("json")
        return FakeResponse()

    import week_trader.brokers.alpaca_paper as alpaca_paper_module

    monkeypatch.setattr(alpaca_paper_module.requests, "post", fake_post)

    from week_trader.paper_order import paper_order

    result = paper_order("submit-intent", log, dry_run=False)
    assert result["broker_calls"] == 1
    assert result["alpaca_order_id"] == "ord-123"
    assert captured["url"] == "https://paper-api.alpaca.markets/v2/orders"
    body = captured["json"]
    assert isinstance(body, dict)
    assert body["symbol"] == "BTCUSD"


def test_paper_order_fail_closed_missing_keys_after_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALPACA_PAPER_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_SECRET", raising=False)
    _write_template_intent("no-keys-intent")
    log = _trade_gate_log(monkeypatch)
    from week_trader.paper_order import PaperOrderError, paper_order

    with pytest.raises(PaperOrderError, match="ALPACA_PAPER_KEY"):
        paper_order("no-keys-intent", log, dry_run=False)
