#!/usr/bin/env python3
"""Generate one parked-strategy replacement bundle (hypothesis + guards + workflow)."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from week_trader.util import repo_root, sha256_file

ROOT = repo_root()


def _spy_prereg(hid: str, symbol: str, manifest_id: str, research: str, spec_q: str) -> dict:
    base = json.loads((ROOT / "hypotheses/spy-equity-tsmom-1d/preregistration.json").read_text())
    base["hypothesis_id"] = hid
    base["data_manifest_id"] = manifest_id
    base["proof_contract"]["citations_ref"] = research
    base["venue_contract"]["allowed_symbols"] = [symbol]
    spec = base["jev_questions"]["spec"]
    spec[0]["id"] = spec_q
    spec[0]["text"] = (
        f"Given state.fields.spec_has_universe_and_timing and "
        f"state.fields.spec_has_cost_manifest_binding and "
        f"state.fields.manifest_single_equity_symbol_matches, "
        f"is the {symbol} daily equity spec falsifiable as written?"
    )
    spec[1]["text"] = spec[1]["text"].replace("SPY", symbol)
    for t in base["jev_questions"]["trade"]:
        t["text"] = t["text"].replace("SPY", symbol)
    return base


def _eth_prereg(hid: str, symbol: str, manifest_id: str, research: str) -> dict:
    base = json.loads((ROOT / "hypotheses/eth-spot-tsmom-4h/preregistration.json").read_text())
    base["hypothesis_id"] = hid
    base["data_manifest_id"] = manifest_id
    base["proof_contract"]["citations_ref"] = research
    base["venue_contract"]["allowed_symbols"] = [symbol]
    return base


def _gld_prereg(hid: str, symbol: str, manifest_id: str, research: str, qid: str) -> dict:
    base = json.loads((ROOT / "hypotheses/gld-negative-attention-1d/preregistration.json").read_text())
    base["hypothesis_id"] = hid
    base["data_manifest_id"] = manifest_id
    base["proof_contract"]["citations_ref"] = research
    base["venue_contract"]["allowed_symbols"] = [symbol]
    base["jev_questions"]["spec"][0]["id"] = qid
    base["jev_questions"]["spec"][0]["text"] = (
        "Given state.fields.spec_has_universe_and_timing and "
        "state.fields.spec_has_cost_manifest_binding and "
        "state.fields.attention_manifest_present, "
        f"is the {symbol} negative-attention spec falsifiable as written?"
    )
    base["jev_questions"]["spec"][2]["state_keys"] = [
        "fields.venue_contract_equity_attention_single",
        "fields.disconfirmers_documented",
        "fields.backtest_metrics_do_not_satisfy_paper_proof",
    ]
    base["jev_questions"]["spec"][2]["text"] = (
        "Given state.fields.venue_contract_equity_attention_single and "
        "state.fields.disconfirmers_documented and "
        "state.fields.backtest_metrics_do_not_satisfy_paper_proof, "
        f"does the spec require Alpaca paper {symbol} forward proof rather than backtest-only promotion?"
    )
    for t in base["jev_questions"]["trade"]:
        t["text"] = t["text"].replace("GLD", symbol)
    return base


def equity_manifest(hid: str, symbol: str) -> str:
    text = (ROOT / "data/manifests/spy-equity-tsmom-1d-alpaca.yaml").read_text()
    return (
        text.replace("spy-equity-tsmom-1d", hid)
        .replace("SPY", symbol)
        .replace("spy", hid.split("-")[0])
    )


def crypto_manifest(hid: str, symbol: str) -> str:
    text = (ROOT / "data/manifests/eth-spot-tsmom-4h-alpaca.yaml").read_text()
    return text.replace("eth-spot-tsmom-4h", hid).replace("ETH/USD", symbol)


def attention_manifest(hid: str, symbol: str, neg: str, base_kw: str) -> str:
    text = (ROOT / "data/manifests/gld-negative-attention-1d-alpaca.yaml").read_text()
    return (
        text.replace("gld-negative-attention-1d", hid)
        .replace("GLD", symbol)
        .replace("gold crash", neg)
        .replace("gold price", base_kw)
        .replace("GLD (SPDR Gold Shares ETF)", f"{symbol} ETF")
    )


def positive_attention_manifest(hid: str, symbol: str, pos: str, base_kw: str) -> str:
    text = attention_manifest(hid, symbol, pos, base_kw)
    block = f"""attention:
  vendor: google_trends_free
  mode: positive_ratio
  positive_keyword: {pos}
  baseline_keyword: {base_kw}
"""
    text = text.replace("  negative_keyword:", "  mode: negative_ratio\n  negative_keyword:")
    if "mode: negative_ratio" not in text:
        text = text.replace("attention:\n  vendor:", block.strip() + "\n  vendor:", 1)
    return text


def guard_json(hid: str, symbol: str) -> dict:
    return {
        "schema_version": 1,
        "hypothesis_id": hid,
        "symbol_owners": {symbol: hid},
        "strategy_slices": {
            hid: {"max_notional_usd": 5000, "fill_tag": f"wt-{hid}"},
        },
    }


def workflow_yml(hid: str, cron: str = "30 21 * * 1-5") -> str:
    return f"""name: paper-forward-{hid}

on:
  schedule:
    - cron: "{cron}"
  workflow_dispatch:

jobs:
  forward:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install
        run: pip install -e ".[dev]"
      - name: Gate 4 closed
        run: make gate4-closed
      - name: Paper forward monitor + live signal + anomaly check
        env:
          ALPACA_PAPER_KEY: ${{{{ secrets.ALPACA_PAPER_KEY }}}}
          ALPACA_PAPER_SECRET: ${{{{ secrets.ALPACA_PAPER_SECRET }}}}
        run: |
          set -euo pipefail
          ID={hid}
          paper-forward "ID=${{ID}}" CHECK_ALERTS=1
          paper-forward "ID=${{ID}}" "ACTION=signal" "CLOSES=live"
          paper-forward "ID=${{ID}}" ACTION=alerts
      - name: Fail on critical forward anomalies
        run: |
          python - <<'PY'
          import json
          from pathlib import Path
          path = Path("paper/{hid}/forward/alerts.json")
          if not path.is_file():
              raise SystemExit("alerts.json missing")
          report = json.loads(path.read_text(encoding="utf-8"))
          if report.get("severity") == "critical":
              raise SystemExit(report.get("alerts"))
          print("severity", report.get("severity"))
          PY
      - name: Upload forward artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: paper-forward-{hid}
          path: |
            paper/{hid}/forward/status.json
            paper/{hid}/forward/alerts.json
            paper/{hid}/forward/events.jsonl
          if-no-files-found: ignore
"""


def crypto_workflow(hid: str) -> str:
    return workflow_yml(hid, cron="15 */4 * * *")


def freeze(hid: str, manifest_rel: str) -> None:
    hdir = ROOT / "hypotheses" / hid
    data = {
        "schema_version": 1,
        "hypothesis_id": hid,
        "description": "Bind HYPOTHESIS.md, full preregistration.json, and data manifest before backtest or Jev.",
        "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "artifacts": {
            "HYPOTHESIS.md": f"sha256:{sha256_file(hdir / 'HYPOTHESIS.md')}",
            "preregistration.json": f"sha256:{sha256_file(hdir / 'preregistration.json')}",
            "data_manifest": {
                "path": manifest_rel,
                "sha256": f"sha256:{sha256_file(ROOT / manifest_rel)}",
            },
        },
    }
    (hdir / "freeze_manifest.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_hypothesis_md(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec_json", help="JSON spec file path")
    args = parser.parse_args()
    spec = json.loads(Path(args.spec_json).read_text())
    hid = spec["id"]
    hdir = ROOT / "hypotheses" / hid
    hdir.mkdir(parents=True, exist_ok=True)
    manifest_rel = f"data/manifests/{hid}-alpaca.yaml"
    write_hypothesis_md(hdir / "HYPOTHESIS.md", spec["hypothesis_md"])
    (ROOT / manifest_rel).write_text(spec["manifest_yaml"], encoding="utf-8")
    (hdir / "preregistration.json").write_text(
        json.dumps(spec["prereg"], indent=2) + "\n", encoding="utf-8"
    )
    freeze(hid, manifest_rel)
    (ROOT / "docs/intake" / f"{hid}-research.md").write_text(spec["research_md"], encoding="utf-8")
    guard_path = ROOT / "config/paper_guards" / f"{hid}.json"
    guard_path.parent.mkdir(parents=True, exist_ok=True)
    guard_path.write_text(json.dumps(spec["guard"], indent=2) + "\n", encoding="utf-8")
    wf = ROOT / ".github/workflows" / f"paper-forward-{hid}.yml"
    wf.write_text(spec["workflow_yml"], encoding="utf-8")
    print("generated", hid)


if __name__ == "__main__":
    main()
