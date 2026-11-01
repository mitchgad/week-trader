from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from week_trader.forward_pnl_adjustments import (
    build_forward_pnl_adjustments,
    estimate_fill_costs_usd,
    shares_before_ex_date,
)


def test_estimate_fill_costs_uses_manifest_bps_per_side() -> None:
    fills = [
        {
            "status": "filled",
            "filled_qty": "10",
            "filled_avg_price": "100",
            "side": "buy",
        }
    ]
    # 10 * 100 = 1000 notional; (2 + 3) bps = 5 bps => 0.50 USD
    total = estimate_fill_costs_usd(fills, fee_bps=2.0, slippage_bps=3.0)
    assert total == pytest.approx(0.5)


def test_shares_before_ex_date_from_buy_and_sell_fills() -> None:
    fills = [
        {
            "symbol": "SPY",
            "side": "buy",
            "filled_qty": "5",
            "filled_at": "2025-06-01T20:00:00Z",
        },
        {
            "symbol": "SPY",
            "side": "sell",
            "filled_qty": "2",
            "filled_at": "2025-08-01T20:00:00Z",
        },
    ]
    assert shares_before_ex_date(fills, "SPY", date(2025, 7, 1)) == pytest.approx(5.0)
    assert shares_before_ex_date(fills, "SPY", date(2025, 9, 1)) == pytest.approx(3.0)


def test_build_forward_pnl_adjustments_side_by_side(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = Path(__file__).resolve().parents[1]
    hypothesis_id = "spy-equity-tsmom-1d"
    for name in ("HYPOTHESIS.md", "preregistration.json", "freeze_manifest.json"):
        src = repo / "hypotheses" / hypothesis_id / name
        dest = tmp_path / "hypotheses" / hypothesis_id / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8"))
    (tmp_path / "data" / "manifests").mkdir(parents=True, exist_ok=True)
    manifest_src = repo / "data" / "manifests" / "spy-equity-tsmom-1d-alpaca.yaml"
    (tmp_path / "data" / "manifests" / "spy-equity-tsmom-1d-alpaca.yaml").write_text(
        manifest_src.read_text(encoding="utf-8")
    )

    for target in (
        "week_trader.util.repo_root",
        "week_trader.manifest.repo_root",
    ):
        monkeypatch.setattr(target, lambda: tmp_path)

    forward = tmp_path / "paper" / hypothesis_id / "forward"
    forward.mkdir(parents=True)
    (forward / "events.jsonl").write_text(
        '{"event_type":"fill","timestamp_utc":"2025-06-01T00:00:00Z","payload":{'
        '"status":"filled","symbol":"SPY","side":"buy","filled_qty":"10",'
        '"filled_avg_price":"500","filled_at":"2025-06-01T20:00:00Z"}}\n',
        encoding="utf-8",
    )

    def fake_dividends(_symbols: list[str], **kwargs: object) -> list[dict[str, object]]:
        return [
            {
                "id": "div-1",
                "symbol": "SPY",
                "ex_date": "2025-09-19",
                "rate": 1.25,
            }
        ]

    view = build_forward_pnl_adjustments(
        hypothesis_id,
        raw_snapshot={
            "equity": 10000.0,
            "last_equity": 9900.0,
            "cash": 5000.0,
            "buying_power": 5000.0,
            "unrealized_pl": 50.0,
        },
        positions=[{"symbol": "SPY", "qty": "10"}],
        forward_directory=forward,
        fetch_dividends=fake_dividends,
        synced_utc="2025-10-01T00:00:00Z",
    )

    assert view["raw"]["equity"] == 10000.0
    # 10 shares * 1.25 dividend = 12.5; fill cost 10*500*(0+2)/10000 = 1.0
    assert view["adjustments"]["cumulative_dividends_usd"] == pytest.approx(12.5)
    assert view["adjustments"]["cumulative_estimated_costs_usd"] == pytest.approx(1.0)
    assert view["adjusted"]["equity"] == pytest.approx(10000.0 + 12.5 - 1.0)
    assert (forward / "dividend_ledger.json").is_file()
