from __future__ import annotations

from pathlib import Path
from typing import Any

from week_trader.util import load_json, repo_root


class PaperGuardsConfigError(Exception):
    pass


def hypothesis_guard_config_path(hypothesis_id: str) -> Path:
    return repo_root() / "config" / "paper_guards" / f"{hypothesis_id}.json"


def load_hypothesis_guard_overlay(hypothesis_id: str) -> dict[str, Any] | None:
    path = hypothesis_guard_config_path(hypothesis_id)
    if not path.is_file():
        return None
    data = load_json(path)
    if not isinstance(data, dict):
        raise PaperGuardsConfigError(f"{path} must be a JSON object")
    return data


def merged_guard_view(hypothesis_id: str, base_config: dict[str, Any]) -> dict[str, Any]:
    """Merge config/paper_guards/<id>.json over paper_account_guards.json for one hypothesis."""
    overlay = load_hypothesis_guard_overlay(hypothesis_id)
    if overlay is None:
        return base_config
    owners = dict(base_config.get("symbol_owners") or {})
    overlay_owners = overlay.get("symbol_owners")
    if isinstance(overlay_owners, dict):
        owners.update(overlay_owners)
    slices = dict(base_config.get("strategy_slices") or {})
    slice_entry = overlay.get("strategy_slice")
    if isinstance(slice_entry, dict):
        slices[hypothesis_id] = slice_entry
    return {**base_config, "symbol_owners": owners, "strategy_slices": slices}
