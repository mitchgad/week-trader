from __future__ import annotations

from pathlib import Path

import yaml

from week_trader.util import repo_root


class Gate4Error(Exception):
    pass


def assert_gate4_closed() -> None:
    path = repo_root() / "gates" / "gate4-checklist.yaml"
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if data.get("v1_policy") != "live_impossible":
        raise Gate4Error("v1_policy must be live_impossible")

    items = data.get("items") or []
    for item in items:
        status = item.get("status")
        if status != "blocked_v1":
            raise Gate4Error(f"item {item.get('id')} must be blocked_v1, got {status!r}")

    live_markers = _scan_for_live_connectors()
    if live_markers:
        raise Gate4Error("live connector markers found: " + ", ".join(live_markers))


def _scan_for_live_connectors() -> list[str]:
    """Phase 1: fail if live broker connector modules appear (not guard code)."""
    root = repo_root()
    hits: list[str] = []
    for path in (root / "week_trader").rglob("*.py"):
        name = path.name
        if name in {"gate4.py", "paper_order.py", "typesafe_client.py"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "LIVE_BROKER" in text or "live-api.alpaca.markets" in text:
            hits.append(str(path.relative_to(root)))
    return hits
