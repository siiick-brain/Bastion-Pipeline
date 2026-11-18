"""Writes the SonarCloud quality gate result for one commit as release gate evidence.

The SonarCloud control is advisory. The file is written only when SonarCloud has analysed the
released commit: "PASS", or "FAIL: <failed conditions>". With no analysis or no network the file
is not written, so the release gate reports the control as NOT VERIFIED.

Usage: python -m scripts.release.sonar_status --revision <sha> --out evidence/sonarcloud.txt
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

API = "https://sonarcloud.io/api"
Fetcher = Callable[[str], dict[str, Any]]


def https_json(url: str) -> dict[str, Any]:
    if not url.startswith("https://"):
        raise ValueError("refusing non-HTTPS URL")
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 - scheme checked
        data: dict[str, Any] = json.load(resp)
        return data


def project_key(properties: Path) -> str:
    for line in properties.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "sonar.projectKey":
            return value.strip()
    raise ValueError(f"sonar.projectKey not found in {properties}")


def status_for(project: str, revision: str, fetch: Fetcher) -> str | None:
    query = urllib.parse.urlencode({"project": project, "branch": "main", "ps": 100})
    analyses = fetch(f"{API}/project_analyses/search?{query}").get("analyses", [])
    match = next((a for a in analyses if a.get("revision") == revision), None)
    if match is None:
        return None
    gate_query = urllib.parse.urlencode({"analysisId": match["key"]})
    gate = fetch(f"{API}/qualitygates/project_status?{gate_query}").get("projectStatus", {})
    if gate.get("status") == "OK":
        return "PASS"
    failed = [c["metricKey"] for c in gate.get("conditions", []) if c.get("status") == "ERROR"]
    return "FAIL: " + (", ".join(failed) or str(gate.get("status")))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--revision", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--properties", type=Path, default=Path("sonar-project.properties"))
    args = ap.parse_args(argv)
    try:
        result = status_for(project_key(args.properties), args.revision, https_json)
    # Advisory: an unreadable reply leaves the control NOT VERIFIED.
    except (OSError, ValueError, KeyError, AttributeError, TypeError) as exc:
        print(f"SonarCloud status unavailable ({type(exc).__name__}); control stays NOT VERIFIED")
        return 0
    if result is None:
        print(f"No SonarCloud analysis for {args.revision}; control stays NOT VERIFIED")
        return 0
    args.out.write_text(result + "\n", encoding="utf-8")
    print(f"SonarCloud quality gate: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
