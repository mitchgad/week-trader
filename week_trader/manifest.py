from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from week_trader.util import repo_root


class ManifestError(Exception):
    pass


def load_data_manifest(manifest_path: Path) -> dict[str, Any]:
    with manifest_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ManifestError("manifest must be a mapping")
    return data


def resolve_manifest_for_hypothesis(hypothesis_id: str, prereg: dict[str, Any]) -> Path:
    manifest_id = prereg.get("data_manifest_id")
    manifests_dir = repo_root() / "data" / "manifests"
    candidate = manifests_dir / f"{manifest_id}.yaml"
    if candidate.is_file():
        return candidate

    freeze_path = repo_root() / "hypotheses" / hypothesis_id / "freeze_manifest.json"
    if freeze_path.is_file():
        import json

        freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
        rel = freeze.get("artifacts", {}).get("data_manifest", {}).get("path")
        if rel:
            path = Path(rel)
            if not path.is_absolute():
                path = repo_root() / path
            if path.is_file():
                return path

    raise ManifestError(f"data manifest not found for id {manifest_id!r}")


def validate_manifest_costs(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    costs = manifest.get("costs")
    if not isinstance(costs, dict):
        return ["costs block missing"]

    for key in ("fee_bps_per_side", "slippage_bps_per_side"):
        if key not in costs:
            errors.append(f"costs.{key} required")

    instrument = manifest.get("instrument_class")
    venue = manifest.get("venue_contract", {})
    if instrument == "crypto_perp":
        for key in ("funding_interval_hours", "funding_series_id"):
            if costs.get(key) in (None, ""):
                errors.append(f"costs.{key} required for crypto_perp")

    paper_venue = venue.get("paper_venue") if isinstance(venue, dict) else None
    if instrument == "crypto_perp" and paper_venue == "alpaca_paper":
        errors.append("Alpaca paper cannot validate crypto_perp funding — change paper_venue")

    if not manifest.get("universe", {}).get("point_in_time"):
        errors.append("universe.point_in_time must be true")

    return errors


def validate_manifest_file(path: Path) -> list[str]:
    try:
        manifest = load_data_manifest(path)
    except (OSError, yaml.YAMLError) as exc:
        return [f"failed to load manifest: {exc}"]
    return validate_manifest_costs(manifest)
