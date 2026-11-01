from __future__ import annotations

import json
from pathlib import Path

import pytest

from week_trader.paper_account_guards import load_guards_config, strategy_slice
from week_trader.paper_order import PaperOrderError, _load_order_intent, _reject_live_alpaca_urls_in_intent
from week_trader.prereg import load_preregistration
from week_trader.util import load_json, repo_root


PAPER_HOST = "https://paper-api.alpaca.markets"

# hypothesis_id, intent_id, side, symbol, qty, reference_price_usd, max_notional_usd (from guards)
STRATEGY_ORDER_INTENTS: list[tuple[str, str, str, str, str, float, float]] = [
    ("eth-spot-tsmom-4h", "market-long-ethusd", "buy", "ETHUSD", "0.5", 3500.0, 2500.0),
    ("spy-equity-tsmom-1d", "market-long-spy", "buy", "SPY", "8", 550.0, 5000.0),
    ("gld-negative-attention-1d", "market-long-gld", "buy", "GLD", "18", 240.0, 5000.0),
    ("dia-mean-reversion-1d", "market-long-dia", "buy", "DIA", "10", 440.0, 5000.0),
    ("eem-xlf-csmom-1d", "market-long-eem", "buy", "EEM", "100", 42.0, 5000.0),
    ("eem-xlf-csmom-1d", "market-long-xlf", "buy", "XLF", "100", 44.0, 5000.0),
    ("tlt-ief-pairs-1d", "market-long-ief", "buy", "IEF", "50", 95.0, 5000.0),
    ("tlt-ief-pairs-1d", "market-long-tlt", "buy", "TLT", "50", 90.0, 5000.0),
    ("tlt-ief-pairs-1d", "market-short-ief", "sell", "IEF", "50", 95.0, 5000.0),
    ("tlt-ief-pairs-1d", "market-short-tlt", "sell", "TLT", "50", 90.0, 5000.0),
    ("vgit-shy-term-carry-1d", "market-long-vgit", "buy", "VGIT", "80", 58.0, 5000.0),
    ("vgit-shy-term-carry-1d", "market-short-shy", "sell", "SHY", "58", 82.0, 5000.0),
    ("qqq-volume-confirm-1d", "market-long-qqq", "buy", "QQQ", "9", 490.0, 5000.0),
    ("crypto-alts-csmom-4h", "market-long-solusd", "buy", "SOLUSD", "25", 180.0, 5000.0),
    ("crypto-alts-csmom-4h", "market-long-ltcusd", "buy", "LTCUSD", "65", 70.0, 5000.0),
    ("crypto-alts-csmom-4h", "market-long-avaxusd", "buy", "AVAXUSD", "180", 25.0, 5000.0),
    ("slv-negative-attention-1d", "market-long-slv", "buy", "SLV", "170", 28.0, 5000.0),
    ("mara-positive-attention-1d", "market-long-mara", "buy", "MARA", "300", 15.0, 5000.0),
    ("xbi-max-short-1d", "market-short-xbi", "sell", "XBI", "50", 95.0, 5000.0),
    ("vb-vv-size-spread-1d", "market-long-vb", "buy", "VB", "22", 210.0, 5000.0),
    ("vb-vv-size-spread-1d", "market-short-vv", "sell", "VV", "18", 260.0, 5000.0),
]


@pytest.mark.parametrize(
    "hypothesis_id,intent_id,side,symbol,qty,reference_price_usd,max_notional_usd",
    STRATEGY_ORDER_INTENTS,
)
def test_strategy_order_intent_loads_and_fits_slice(
    hypothesis_id: str,
    intent_id: str,
    side: str,
    symbol: str,
    qty: str,
    reference_price_usd: float,
    max_notional_usd: float,
) -> None:
    intent = _load_order_intent(hypothesis_id, intent_id)
    assert intent["side"] == side
    assert str(intent["symbol"]).upper() == symbol
    assert intent["qty"] == qty
    assert float(intent["reference_price_usd"]) == reference_price_usd
    assert intent.get("paper_api_host") == PAPER_HOST

    prereg = load_preregistration(hypothesis_id)
    from week_trader.paper_order import _validate_order_intent

    _validate_order_intent(hypothesis_id, intent, prereg)

    guards = load_guards_config()
    slice_entry = strategy_slice(guards, hypothesis_id)
    assert float(slice_entry["max_notional_usd"]) == max_notional_usd
    projected = float(qty) * reference_price_usd
    assert projected <= max_notional_usd


def test_order_intent_rejects_live_alpaca_host() -> None:
    intent = {
        "symbol": "SPY",
        "side": "buy",
        "qty": "1",
        "paper_api_host": "https://api.alpaca.markets",
    }
    with pytest.raises(PaperOrderError, match="live Alpaca"):
        _reject_live_alpaca_urls_in_intent(intent)


def test_order_intent_rejects_live_order_url() -> None:
    intent = {
        "symbol": "SPY",
        "side": "buy",
        "qty": "1",
        "order_url": "https://api.alpaca.markets/v2/orders",
    }
    with pytest.raises(PaperOrderError, match="live Alpaca"):
        _reject_live_alpaca_urls_in_intent(intent)


def test_each_hypothesis_has_at_least_one_intent_on_disk() -> None:
    expected_hids = sorted({row[0] for row in STRATEGY_ORDER_INTENTS})
    assert len(expected_hids) == 13
    for hid in expected_hids:
        intents_dir = repo_root() / "paper" / hid / "intents"
        files = sorted(p for p in intents_dir.glob("*.json") if not p.name.startswith("_"))
        assert files, f"missing intents for {hid}"


def test_intent_files_are_valid_json() -> None:
    for hypothesis_id, intent_id, *_rest in STRATEGY_ORDER_INTENTS:
        path = repo_root() / "paper" / hypothesis_id / "intents" / f"{intent_id}.json"
        assert path.is_file()
        data = load_json(path)
        assert isinstance(data, dict)
        raw = path.read_text(encoding="utf-8")
        assert json.loads(raw) == data
