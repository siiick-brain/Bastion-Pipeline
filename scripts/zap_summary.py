"""Prints ZAP alert counts by risk from a ZAP JSON report. Usage: zap_summary.py report.json"""

from __future__ import annotations

import json
import sys
from collections import Counter


def summarise(report: dict[str, object]) -> Counter[str]:
    counts: Counter[str] = Counter()
    sites = report.get("site", [])
    if not isinstance(sites, list):
        raise TypeError("ZAP report 'site' must be a list")
    for site in sites:
        for alert in site.get("alerts", []):
            counts[alert["riskdesc"].split(" ")[0]] += 1
    return counts


def main(argv: list[str]) -> int:
    with open(argv[1], encoding="utf-8") as fh:
        counts = summarise(json.load(fh))
    print("| Risk | Alert types |\n| --- | --- |")
    for risk in ("High", "Medium", "Low", "Informational"):
        print(f"| {risk} | {counts.get(risk, 0)} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
