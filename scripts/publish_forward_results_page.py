"""Build a static HTML summary from latest GitHub Actions forward artifacts (no secrets)."""

from __future__ import annotations

import argparse
import html
import io
import json
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from week_trader.forward_health import hypothesis_workflow_filename
from week_trader.forward_track_record import ACTIVE_FORWARD_HYPOTHESIS_IDS

REPO_ROOT = Path(__file__).resolve().parents[1]


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "week-trader-forward-results-page",
    }


def _get_json(url: str, token: str) -> Any:
    req = Request(url, headers=_github_headers(token))
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_bytes(url: str, token: str) -> bytes:
    req = Request(url, headers=_github_headers(token))
    with urlopen(req, timeout=120) as resp:
        return resp.read()


def _latest_run_for_workflow(owner: str, repo: str, workflow_file: str, token: str) -> dict[str, Any] | None:
    base = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_file}/runs"
    params = "branch=main&status=completed&per_page=5&exclude_pull_requests=true"
    data = _get_json(f"{base}?{params}", token)
    runs = data.get("workflow_runs") or []
    for run in runs:
        if run.get("conclusion") == "success":
            return run
    return runs[0] if runs else None


def _list_artifact_zips(run_id: int, owner: str, repo: str, token: str) -> list[tuple[str, str]]:
    """Return (name, archive_download_url) for each artifact."""
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
    data = _get_json(url, token)
    out: list[tuple[str, str]] = []
    for art in data.get("artifacts", []):
        name = str(art.get("name", ""))
        dl = art.get("archive_download_url")
        if isinstance(dl, str) and dl:
            out.append((name, dl))
    return out


def _extract_matching_forward(
    zip_bytes: bytes, hypothesis_id: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    """Return (status, alerts, evidence_lines) from artifact zip if paths match."""
    prefix = f"paper/{hypothesis_id}/forward/"
    status: dict[str, Any] | None = None
    alerts: dict[str, Any] | None = None
    evidence: list[str] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if not name.startswith(prefix):
                continue
            rel = name[len(prefix) :]
            try:
                raw = zf.read(name).decode("utf-8")
            except (OSError, ValueError, UnicodeDecodeError):
                continue
            if rel == "status.json":
                try:
                    status = json.loads(raw)
                except json.JSONDecodeError:
                    status = None
            elif rel == "alerts.json":
                try:
                    alerts = json.loads(raw)
                except json.JSONDecodeError:
                    alerts = None
            elif rel == "events.jsonl":
                lines = [ln for ln in raw.splitlines() if ln.strip()]
                for ln in reversed(lines[-400:]):
                    try:
                        ev = json.loads(ln)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("event_type") == "signal":
                        evidence.append(ln.strip())
                        break
    return status, alerts, evidence


def _artifact_priority(hypothesis_id: str, artifact_name: str) -> int:
    """Higher = preferred (newer / richer artifact names)."""
    if hypothesis_id == "btc-spot-tsmom-4h":
        if "4h-cycle" in artifact_name:
            return 20
        if artifact_name.endswith("paper-forward-btc-spot-tsmom-4h") or artifact_name == "paper-forward-btc-spot-tsmom-4h":
            return 15
        if "hourly" in artifact_name:
            return 10
    if artifact_name == f"paper-forward-{hypothesis_id}":
        return 5
    return 1


@dataclass
class StrategySnapshot:
    hypothesis_id: str
    run_url: str | None
    run_at_utc: str | None
    status: dict[str, Any] | None
    alerts: dict[str, Any] | None
    last_signal_line: str | None
    error: str | None = None


def _collect_strategy(
    owner: str, repo: str, hypothesis_id: str, token: str
) -> StrategySnapshot:
    wf = hypothesis_workflow_filename(hypothesis_id)
    try:
        run = _latest_run_for_workflow(owner, repo, wf, token)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return StrategySnapshot(hypothesis_id, None, None, None, None, None, error=str(exc))

    if run is None:
        return StrategySnapshot(hypothesis_id, None, None, None, None, None, error="no completed runs")

    run_url = str(run.get("html_url", "") or "")
    run_at = str(run.get("run_started_at") or run.get("created_at") or "")
    run_id = int(run["id"])
    zips = _list_artifact_zips(run_id, owner, repo, token)
    best_status: dict[str, Any] | None = None
    best_alerts: dict[str, Any] | None = None
    best_signal: str | None = None
    best_key = -1
    for art_name, art_url in zips:
        key = _artifact_priority(hypothesis_id, art_name)
        if key < best_key:
            continue
        try:
            blob = _get_bytes(art_url, token)
        except (HTTPError, URLError, TimeoutError):
            continue
        st, al, ev_lines = _extract_matching_forward(blob, hypothesis_id)
        if st is None and al is None and not ev_lines:
            continue
        best_key = key
        best_status = st or best_status
        best_alerts = al or best_alerts
        best_signal = ev_lines[0] if ev_lines else best_signal

    return StrategySnapshot(
        hypothesis_id,
        run_url or None,
        run_at or None,
        best_status,
        best_alerts,
        best_signal,
        error=None,
    )


def _collect_health(owner: str, repo: str, token: str) -> dict[str, Any] | None:
    wf = "paper-forward-health.yml"
    run = _latest_run_for_workflow(owner, repo, wf, token)
    if run is None:
        return None
    run_id = int(run["id"])
    for _name, art_url in _list_artifact_zips(run_id, owner, repo, token):
        try:
            blob = _get_bytes(art_url, token)
        except (HTTPError, URLError, TimeoutError):
            continue
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            for path in zf.namelist():
                if path.endswith(("paper/_shared/forward_health.json", "forward_health.json")):
                    try:
                        return json.loads(zf.read(path).decode("utf-8"))
                    except (json.JSONDecodeError, OSError, ValueError):
                        continue
    return None


def _parse_repo(repo: str) -> tuple[str, str]:
    parts = repo.split("/", 1)
    if len(parts) != 2:
        raise SystemExit("GITHUB_REPOSITORY must be owner/name")
    return parts[0], parts[1]


def _signal_summary(last_signal_json: str | None) -> str:
    if not last_signal_json:
        return "—"
    try:
        ev = json.loads(last_signal_json)
    except json.JSONDecodeError:
        return html.escape(last_signal_json[:500])
    payload = ev.get("payload")
    if isinstance(payload, dict):
        side = payload.get("side", payload.get("signal_side"))
        flat = payload.get("flat")
        parts = [f"side={side}", f"flat={flat}"]
        return html.escape(" · ".join(str(p) for p in parts if p is not None))
    return html.escape(json.dumps(payload, sort_keys=True)[:800])


def _alerts_summary(alerts: dict[str, Any] | None) -> str:
    if not alerts:
        return "—"
    sev = alerts.get("severity", "—")
    ac = alerts.get("alert_count", len(alerts.get("alerts") or []))
    return html.escape(f"severity={sev} · alert_count={ac}")


def _status_order_snippet(status: dict[str, Any] | None) -> str:
    if not status:
        return "—"
    book = status.get("account_book")
    rows: list[str] = []
    if isinstance(book, dict):
        oo = book.get("open_orders") or []
        if isinstance(oo, list) and oo:
            o = oo[0]
            if isinstance(o, dict):
                rows.append(
                    f"open_order id={o.get('id')} {o.get('side')} {o.get('qty')} {o.get('symbol')}"
                )
    fills = status.get("fills_synced_this_tick")
    if fills:
        rows.append(f"fills_synced_this_tick={fills}")
    last_side = status.get("last_signal_side")
    if last_side is not None:
        rows.append(f"last_signal_side={last_side}")
    return html.escape(" · ".join(rows)) if rows else "—"


def build_html(
    *,
    owner: str,
    repo: str,
    token: str,
    generated_utc: str,
) -> str:
    health = _collect_health(owner, repo, token)
    strategies = [_collect_strategy(owner, repo, hid, token) for hid in ACTIVE_FORWARD_HYPOTHESIS_IDS]

    health_block = ""
    if health:
        health_block = (
            f"<p><strong>Health</strong> (API): severity={html.escape(str(health.get('severity', '?')))} · "
            f"findings={html.escape(str(health.get('finding_count', '?')))}</p>"
        )
    else:
        health_block = "<p><strong>Health</strong>: no forward_health.json in latest artifact.</p>"

    rows = []
    for s in strategies:
        run_link = (
            f'<a href="{html.escape(s.run_url)}">run</a>' if s.run_url else "—"
        )
        hid_cell = html.escape(s.hypothesis_id)
        if s.error:
            hid_cell += f'<p class="err">{html.escape(s.error)}</p>'
        rows.append(
            "<tr>"
            f"<td>{hid_cell}</td>"
            f"<td>{html.escape(s.run_at_utc or '—')}</td>"
            f"<td>{run_link}</td>"
            f"<td>{_signal_summary(s.last_signal_line)}</td>"
            f"<td>{_alerts_summary(s.alerts)}</td>"
            f"<td>{_status_order_snippet(s.status)}</td>"
            "</tr>"
        )

    title = f"{owner}/{repo} — paper forward results"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1.5rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.5rem; vertical-align: top; }}
    th {{ background: #f4f4f4; text-align: left; }}
    .meta {{ color: #444; font-size: 0.9rem; margin-bottom: 1rem; }}
    .err {{ color: #a00; font-size: 0.85rem; }}
    a {{ color: #06c; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p class="meta">Generated UTC: {html.escape(generated_utc)} · Source: GitHub Actions API + artifacts only (no broker secrets).</p>
  {health_block}
  <h2>Strategies</h2>
  <table>
    <thead>
      <tr>
        <th>Strategy</th>
        <th>Run started (UTC)</th>
        <th>Workflow run</th>
        <th>Signal (latest)</th>
        <th>Forward anomalies</th>
        <th>Paper order / book</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
  <p class="meta">Gate 4 remains blocked in v1. This page is observational only.</p>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "docs" / "forward-results",
        help="Output directory for index.html",
    )
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    if not args.repo:
        raise SystemExit("GITHUB_REPOSITORY or --repo owner/name is required")
    owner, repo = _parse_repo(args.repo)
    from datetime import UTC, datetime

    generated = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    html_out = build_html(owner=owner, repo=repo, token=token, generated_utc=generated)
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    index = out_dir / "index.html"
    index.write_text(html_out, encoding="utf-8")
    print(index)


if __name__ == "__main__":
    main()
