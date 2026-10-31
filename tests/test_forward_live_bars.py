from __future__ import annotations

import json
from pathlib import Path

import pytest

from week_trader.brokers.alpaca_paper import (
    AlpacaPaperError,
    fetch_crypto_4h_bar_closes,
    require_alpaca_data_host,
)
from week_trader.forward_anomalies import check_forward_anomalies
from week_trader.paper_forward import record_signal_from_live_bars, run_forward_monitor_with_alerts


def test_require_alpaca_data_host_refuses_paper_trading_host() -> None:
    with pytest.raises(AlpacaPaperError, match="refusing non-data"):
        require_alpaca_data_host("https://paper-api.alpaca.markets")


def test_fetch_crypto_4h_bar_closes_parses_series(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_KEY", "k")
    monkeypatch.setenv("ALPACA_PAPER_SECRET", "s")

    class FakeResponse:
        status_code = 200
        content = b"{}"

        @staticmethod
        def json() -> dict[str, object]:
            return {
                "bars": {
                    "BTC/USD": [{"c": 100.0 + i} for i in range(8)],
                }
            }

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        assert "data.alpaca.markets" in url
        params = kwargs.get("params")
        assert isinstance(params, dict)
        assert params.get("timeframe") == "4Hour"
        return FakeResponse()

    import week_trader.brokers.alpaca_paper as mod

    monkeypatch.setattr(mod.requests, "get", fake_get)
    closes = fetch_crypto_4h_bar_closes("BTC/USD", min_bars=8)
    assert closes == [100.0 + i for i in range(8)]


def test_record_signal_from_live_bars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("week_trader.paper_forward.repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        "week_trader.paper_forward.fetch_live_4h_closes",
        lambda _hid, min_bars=8: [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0],
    )
    monkeypatch.setattr(
        "week_trader.paper_forward.manifest_crypto_symbol",
        lambda _hid: "BTC/USD",
    )
    out = record_signal_from_live_bars("btc-spot-tsmom-4h")
    assert out["recorded"] is True
    assert out["signal"]["side"] == "long"
    assert out["signal"]["closes_source"] == "alpaca_live_4h"
    events = (tmp_path / "paper" / "btc-spot-tsmom-4h" / "forward" / "events.jsonl").read_text()
    assert "signal" in events


def test_check_forward_anomalies_stale_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("week_trader.forward_anomalies.repo_root", lambda: tmp_path)
    monkeypatch.setattr("week_trader.paper_forward.repo_root", lambda: tmp_path)
    hypothesis_id = "_template"
    forward = tmp_path / "paper" / hypothesis_id / "forward"
    forward.mkdir(parents=True)
    forward.joinpath("status.json").write_text(
        json.dumps({"timestamp_utc": "2020-01-01T00:00:00Z", "account_equity": 1000}) + "\n",
        encoding="utf-8",
    )
    report = check_forward_anomalies(hypothesis_id)
    codes = {a["code"] for a in report["alerts"]}
    assert "stale_status" in codes
    assert (forward / "alerts.json").is_file()


def test_monitor_with_alerts_includes_severity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("week_trader.paper_forward.repo_root", lambda: tmp_path)
    monkeypatch.setattr("week_trader.forward_anomalies.repo_root", lambda: tmp_path)

    def fake_account() -> dict[str, object]:
        return {"equity": "10000", "cash": "5000", "last_equity": "9900"}

    def fake_positions() -> list[dict[str, object]]:
        return []

    result = run_forward_monitor_with_alerts(
        "_template",
        fetch_account=fake_account,
        fetch_positions=fake_positions,
        fetch_order=lambda _oid: {"status": "canceled"},
    )
    assert "anomaly_severity" in result
    assert result["validation_mode"] == "forward_paper_only"


def test_manifest_crypto_symbol_requires_4h(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from week_trader.paper_forward import manifest_crypto_symbol

    repo = Path(__file__).resolve().parents[1]
    monkeypatch.setattr("week_trader.paper_forward.repo_root", lambda: repo)
    assert manifest_crypto_symbol("btc-spot-tsmom-4h") == "BTC/USD"
