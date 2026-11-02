from __future__ import annotations

import json
import sys

from week_trader.forward_health import format_health_summary, run_paper_forward_health_check


def main() -> None:
    report = run_paper_forward_health_check()
    print(format_health_summary(report))
    print(json.dumps({"severity": report.get("severity"), "finding_count": report.get("finding_count")}))
    if report.get("severity") == "critical":
        raise SystemExit(1)
    print("ok")


if __name__ == "__main__":
    main()
