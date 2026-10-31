from __future__ import annotations

import csv
from pathlib import Path

from week_trader.util import repo_root


class GoldenSliceError(Exception):
    pass


def golden_slice_fixture_path() -> Path:
    return repo_root() / "week_trader" / "fixtures" / "golden_slice_1m.csv"


def load_golden_closes(path: Path | None = None) -> list[float]:
    csv_path = path or golden_slice_fixture_path()
    if not csv_path.is_file():
        raise GoldenSliceError(f"golden slice missing: {csv_path}")
    closes: list[float] = []
    with csv_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            closes.append(float(row["close"]))
    if len(closes) < 2:
        raise GoldenSliceError("golden slice needs at least 2 bars")
    return closes


def primary_buy_hold_net_return(
    *,
    fee_bps_per_side: float,
    slippage_bps_per_side: float,
    fixture_path: Path | None = None,
) -> dict[str, float]:
    """
    Deterministic primary engine: buy at first close, sell at last close, apply per-side costs.
    No signal research — infrastructure parity reference only.
    """
    closes = load_golden_closes(fixture_path)
    entry = closes[0]
    exit_px = closes[-1]
    gross = exit_px / entry - 1.0
    cost_frac = 2.0 * (fee_bps_per_side + slippage_bps_per_side) / 10_000.0
    net = gross - cost_frac
    return {
        "engine": "primary_golden_slice",
        "entry_price": entry,
        "exit_price": exit_px,
        "gross_return": gross,
        "net_return": net,
        "bars": float(len(closes)),
    }
