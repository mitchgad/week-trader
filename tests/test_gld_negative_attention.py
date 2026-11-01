from __future__ import annotations

from week_trader.attention.google_trends import TrendsDailyRow
from week_trader.paper_guards_config import merged_guard_view
from week_trader.strategies.gld_negative_attention_1d import evaluate_gld_negative_attention_1d


def _synthetic_rows(count: int, *, partial_last: bool = False) -> list[TrendsDailyRow]:
    rows: list[TrendsDailyRow] = []
    for i in range(count):
        rows.append(
            TrendsDailyRow(
                date_utc=f"2024-01-{i+1:02d}",
                negative_keyword=10 if i % 5 else 80,
                baseline_keyword=50,
                is_partial=False,
            )
        )
    if partial_last:
        rows.append(
            TrendsDailyRow(
                date_utc="2024-02-01",
                negative_keyword=99,
                baseline_keyword=50,
                is_partial=True,
            )
        )
    return rows


def test_evaluate_gld_negative_attention_high_ratio_flats() -> None:
    rows = _synthetic_rows(260)
    rows[-1] = TrendsDailyRow(
        date_utc="2024-12-31",
        negative_keyword=100,
        baseline_keyword=10,
        is_partial=False,
    )
    signal = evaluate_gld_negative_attention_1d(rows, hypothesis_id="gld-negative-attention-1d")
    assert signal["side"] == "flat"
    assert signal["symbol"] == "GLD"


def test_evaluate_gld_negative_attention_low_ratio_long() -> None:
    rows = [
        TrendsDailyRow(
            date_utc=f"2024-01-{i+1:02d}",
            negative_keyword=20,
            baseline_keyword=50,
            is_partial=False,
        )
        for i in range(259)
    ]
    rows.append(
        TrendsDailyRow(
            date_utc="2024-10-15",
            negative_keyword=1,
            baseline_keyword=50,
            is_partial=False,
        )
    )
    signal = evaluate_gld_negative_attention_1d(rows, hypothesis_id="gld-negative-attention-1d")
    assert signal["side"] == "long"


def test_merged_guard_overlay_adds_gld_slice() -> None:
    base = {
        "symbol_owners": {"BTCUSD": "btc-spot-tsmom-4h"},
        "strategy_slices": {"btc-spot-tsmom-4h": {"max_notional_usd": 5000, "fill_tag": "x"}},
    }
    merged = merged_guard_view(
        "gld-negative-attention-1d",
        base,
    )
    assert merged["symbol_owners"]["GLD"] == "gld-negative-attention-1d"
    assert merged["strategy_slices"]["gld-negative-attention-1d"]["max_notional_usd"] == 5000
    assert merged["strategy_slices"]["btc-spot-tsmom-4h"]["max_notional_usd"] == 5000
