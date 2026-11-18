"""Release gate. Reads evidence files and blocks the release unless every mandatory control passes.

A control is PASS, FAIL or NOT VERIFIED. A mandatory control that is FAIL or NOT VERIFIED blocks.
Optional controls are reported but never block.

Evidence directory layout (missing files make the control NOT VERIFIED):
  coverage.json        pytest-cov JSON report
  junit.xml            pytest JUnit report
  trivy-image.json     Trivy JSON scan of the release image digest
  sbom-check.json      output of scripts.release.sbom_check
  cdx-schema.txt       "PASS" when cyclonedx-cli validate succeeded
  verify.json          {"cosign_verify": ..., "provenance": ..., "sbom_attestation": ...,
                        "windows_signature": ..., "tamper_rejected": ...}
  sonarcloud.txt       optional, "PASS" when the quality gate passed

Usage: python -m scripts.release.gate <evidence-dir> [--exceptions security/exceptions.toml]
       [--summary out.md]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from scripts.release import exceptions as exc_mod

PASS, FAIL, NOT_VERIFIED = "PASS", "FAIL", "NOT VERIFIED"
COVERAGE_MIN = 85.0


@dataclass(frozen=True)
class Result:
    control: str
    status: str
    detail: str
    mandatory: bool = True


def _read_json(path: Path) -> object | None:
    if not path.is_file():
        return None
    data: object = json.loads(path.read_text(encoding="utf-8"))
    return data


def check_tests(ev: Path) -> Result:
    p = ev / "junit.xml"
    if not p.is_file():
        return Result("Unit tests pass", NOT_VERIFIED, "junit.xml missing")
    # Own pytest output; expat resolves no external entities.
    # nosemgrep: python.lang.security.use-defused-xml-parse.use-defused-xml-parse
    root = ET.parse(p).getroot()  # noqa: S314
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = sum(int(s.get("tests", 0)) for s in suites)
    bad = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    if total == 0:
        return Result("Unit tests pass", FAIL, "no tests ran")
    status = PASS if bad == 0 else FAIL
    return Result("Unit tests pass", status, f"{total} tests, {bad} failed or errored")


def check_coverage(ev: Path) -> Result:
    data = _read_json(ev / "coverage.json")
    if not isinstance(data, dict):
        return Result("Coverage at least 85 percent", NOT_VERIFIED, "coverage.json missing")
    pct = float(data["totals"]["percent_covered"])
    status = PASS if pct >= COVERAGE_MIN else FAIL
    return Result("Coverage at least 85 percent", status, f"{pct:.2f} percent")


VULN_CONTROL = "Zero unaccepted critical or high vulnerabilities"


def check_vulns(ev: Path, accepted: list[exc_mod.Exception_]) -> Result:
    name = VULN_CONTROL
    data = _read_json(ev / "trivy-image.json")
    if not isinstance(data, dict):
        return Result(name, NOT_VERIFIED, "trivy-image.json missing")
    found: list[str] = []
    for res in data.get("Results") or []:
        for v in res.get("Vulnerabilities") or []:
            if v.get("Severity") in {"CRITICAL", "HIGH"}:
                vid = v.get("VulnerabilityID", "?")
                if not any(e.covers(vid) for e in accepted):
                    found.append(f"{vid} ({v.get('PkgName')})")
    if found:
        unique = sorted(set(found))
        return Result(name, FAIL, f"{len(unique)} unaccepted: {', '.join(unique[:10])}")
    return Result(name, PASS, f"0 unaccepted, {len(accepted)} register entries")


def _simple(ev: Path, file: str, control: str, mandatory: bool = True) -> Result:
    p = ev / file
    if not p.is_file():
        return Result(control, NOT_VERIFIED, f"{file} missing", mandatory)
    text = p.read_text(encoding="utf-8").strip()
    return Result(control, PASS if text == PASS else FAIL, text[:200], mandatory)


def check_sbom(ev: Path) -> list[Result]:
    data = _read_json(ev / "sbom-check.json")
    if not isinstance(data, dict):
        semantic = Result("SBOMs describe the release digest", NOT_VERIFIED, "missing")
    else:
        status = PASS if data.get("status") == PASS else FAIL
        detail = data.get("error") or (
            f"CycloneDX {data.get('cyclonedx_components')} components, "
            f"SPDX {data.get('spdx_packages')} packages"
        )
        semantic = Result("SBOMs describe the release digest", status, str(detail))
    return [semantic, _simple(ev, "cdx-schema.txt", "CycloneDX schema valid")]


VERIFY_CONTROLS = {
    "cosign_verify": "Image signature, identity and issuer verified",
    "provenance": "Provenance verified (digest, workflow, ref, commit)",
    "sbom_attestation": "SBOM attestations verified",
    "windows_signature": "Windows checksums signature verified",
    "tamper_rejected": "Tampered artifact rejected",
}


def check_verify(ev: Path) -> list[Result]:
    data = _read_json(ev / "verify.json")
    out = []
    for key, label in VERIFY_CONTROLS.items():
        if not isinstance(data, dict) or key not in data:
            out.append(Result(label, NOT_VERIFIED, "no evidence"))
        else:
            value = str(data[key])
            out.append(Result(label, PASS if value == PASS else FAIL, value))
    return out


EVIDENCE_ERRORS = (ValueError, KeyError, TypeError, AttributeError, ET.ParseError, OSError)


def _guard(
    control: str, check: Callable[[], Result | list[Result]], mandatory: bool = True
) -> list[Result]:
    """Malformed evidence fails its control instead of crashing the gate."""
    try:
        r = check()
    except EVIDENCE_ERRORS as e:
        return [Result(control, FAIL, f"unreadable evidence: {type(e).__name__}", mandatory)]
    return r if isinstance(r, list) else [r]


def evaluate(ev: Path, exceptions_path: Path, today: dt.date | None = None) -> list[Result]:
    results: list[Result] = []
    try:
        accepted = exc_mod.load(exceptions_path, today)
        results.append(Result("Exception register valid", PASS, f"{len(accepted)} entries"))
    except (ValueError, TypeError, AttributeError, OSError) as e:
        accepted = []
        results.append(Result("Exception register valid", FAIL, str(e)))
    results += _guard("Unit tests pass", lambda: check_tests(ev))
    results += _guard("Coverage at least 85 percent", lambda: check_coverage(ev))
    results += _guard(VULN_CONTROL, lambda: check_vulns(ev, accepted))
    results += _guard("SBOMs describe the release digest", lambda: check_sbom(ev))
    results += _guard(VERIFY_CONTROLS["cosign_verify"], lambda: check_verify(ev))
    results += _guard(
        "SonarCloud quality gate",
        lambda: _simple(ev, "sonarcloud.txt", "SonarCloud quality gate", mandatory=False),
        mandatory=False,
    )
    return results


def blocked(results: list[Result]) -> bool:
    return any(r.mandatory and r.status != PASS for r in results)


def render(results: list[Result]) -> str:
    lines = ["| Control | Mandatory | Status | Detail |", "| --- | --- | --- | --- |"]
    for r in results:
        detail = r.detail.replace("|", "/")
        lines.append(f"| {r.control} | {'yes' if r.mandatory else 'no'} | {r.status} | {detail} |")
    verdict = "BLOCKED" if blocked(results) else "ALLOWED"
    lines.append(f"\nRelease gate: {verdict}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Release gate")
    ap.add_argument("evidence", type=Path)
    ap.add_argument("--exceptions", type=Path, default=Path("security/exceptions.toml"))
    ap.add_argument("--summary", type=Path)
    args = ap.parse_args(argv)
    results = evaluate(args.evidence, args.exceptions)
    text = render(results)
    print(text)
    if args.summary:
        args.summary.write_text(text + "\n", encoding="utf-8")
    return 1 if blocked(results) else 0


if __name__ == "__main__":
    sys.exit(main())
