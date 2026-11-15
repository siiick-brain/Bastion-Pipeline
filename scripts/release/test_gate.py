from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from scripts.release import exceptions as exc_mod
from scripts.release import gate

TODAY = dt.date(2026, 11, 15)
DIGEST = "sha256:" + "a" * 64

GOOD_EXCEPTIONS = """
[[exception]]
id = "EX-1"
finding = "CVE-2099-0001 (libfoo)"
scope = "image"
reason = "not reachable"
risk = "low"
owner = "owner"
expires = "2027-01-01"
"""


def _write_good_evidence(ev: Path) -> None:
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "junit.xml").write_text(
        '<testsuites><testsuite tests="40" failures="0" errors="0"/></testsuites>'
    )
    (ev / "coverage.json").write_text(json.dumps({"totals": {"percent_covered": 97.5}}))
    (ev / "trivy-image.json").write_text(json.dumps({"Results": [{"Vulnerabilities": []}]}))
    (ev / "sbom-check.json").write_text(
        json.dumps({"status": "PASS", "cyclonedx_components": 20, "spdx_packages": 21})
    )
    (ev / "cdx-schema.txt").write_text("PASS")
    (ev / "verify.json").write_text(json.dumps(dict.fromkeys(gate.VERIFY_CONTROLS, "PASS")))


@pytest.fixture
def setup(tmp_path: Path) -> tuple[Path, Path]:
    ev = tmp_path / "ev"
    _write_good_evidence(ev)
    reg = tmp_path / "exceptions.toml"
    reg.write_text(GOOD_EXCEPTIONS)
    return ev, reg


def _status(results: list[gate.Result], control_prefix: str) -> str:
    return next(r.status for r in results if r.control.startswith(control_prefix))


def test_all_evidence_passes(setup: tuple[Path, Path]) -> None:
    ev, reg = setup
    results = gate.evaluate(ev, reg, TODAY)
    assert not gate.blocked(results)
    assert _status(results, "SonarCloud") == gate.NOT_VERIFIED  # optional, does not block


def test_cli_exit_codes(setup: tuple[Path, Path], tmp_path: Path) -> None:
    ev, reg = setup
    summary = tmp_path / "s.md"
    # Real clock: the fixture expiry is in 2027 so it is valid today.
    assert gate.main([str(ev), "--exceptions", str(reg), "--summary", str(summary)]) == 0
    assert "Release gate: ALLOWED" in summary.read_text()
    (ev / "coverage.json").write_text(json.dumps({"totals": {"percent_covered": 50}}))
    assert gate.main([str(ev), "--exceptions", str(reg)]) == 1


@pytest.mark.parametrize(
    ("file", "content", "control", "expected"),
    [
        ("junit.xml", '<testsuite tests="3" failures="1" errors="0"/>', "Unit tests", "FAIL"),
        ("junit.xml", '<testsuite tests="0" failures="0" errors="0"/>', "Unit tests", "FAIL"),
        ("coverage.json", '{"totals": {"percent_covered": 84.99}}', "Coverage", "FAIL"),
        ("cdx-schema.txt", "FAIL: invalid", "CycloneDX schema", "FAIL"),
        ("sbom-check.json", '{"status": "FAIL", "error": "digest mismatch"}', "SBOMs", "FAIL"),
        ("verify.json", '{"cosign_verify": "FAIL"}', "Image signature", "FAIL"),
        ("verify.json", '{"cosign_verify": "PASS"}', "Provenance", "NOT VERIFIED"),
    ],
)
def test_failing_or_missing_control_blocks(
    setup: tuple[Path, Path], file: str, content: str, control: str, expected: str
) -> None:
    ev, reg = setup
    (ev / file).write_text(content)
    results = gate.evaluate(ev, reg, TODAY)
    assert _status(results, control) == expected
    assert gate.blocked(results)


@pytest.mark.parametrize(
    "missing",
    [
        "junit.xml",
        "coverage.json",
        "trivy-image.json",
        "sbom-check.json",
        "cdx-schema.txt",
        "verify.json",
    ],
)
def test_missing_evidence_is_not_verified_and_blocks(
    setup: tuple[Path, Path], missing: str
) -> None:
    ev, reg = setup
    (ev / missing).unlink()
    results = gate.evaluate(ev, reg, TODAY)
    assert gate.NOT_VERIFIED in {r.status for r in results}
    assert gate.blocked(results)


def _trivy(vulns: list[dict[str, str]]) -> str:
    return json.dumps({"Results": [{"Vulnerabilities": vulns}]})


def test_unaccepted_high_vulnerability_blocks(setup: tuple[Path, Path]) -> None:
    ev, reg = setup
    (ev / "trivy-image.json").write_text(
        _trivy([{"VulnerabilityID": "CVE-2099-9999", "Severity": "HIGH", "PkgName": "x"}])
    )
    results = gate.evaluate(ev, reg, TODAY)
    assert _status(results, "Zero unaccepted") == "FAIL"
    assert gate.blocked(results)


def test_accepted_vulnerability_and_medium_do_not_block(setup: tuple[Path, Path]) -> None:
    ev, reg = setup
    (ev / "trivy-image.json").write_text(
        _trivy(
            [
                {"VulnerabilityID": "CVE-2099-0001", "Severity": "CRITICAL", "PkgName": "libfoo"},
                {"VulnerabilityID": "CVE-2099-5555", "Severity": "MEDIUM", "PkgName": "y"},
            ]
        )
    )
    assert not gate.blocked(gate.evaluate(ev, reg, TODAY))


def test_expired_exception_blocks(setup: tuple[Path, Path]) -> None:
    ev, reg = setup
    later = dt.date(2027, 1, 2)
    results = gate.evaluate(ev, reg, later)
    assert _status(results, "Exception register") == "FAIL"
    assert gate.blocked(results)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (GOOD_EXCEPTIONS.replace('owner = "owner"\n', ""), "missing owner"),
        (GOOD_EXCEPTIONS.replace('reason = "not reachable"', 'reason = ""'), "missing reason"),
        (GOOD_EXCEPTIONS.replace("2027-01-01", "not-a-date"), "invalid expires"),
        (GOOD_EXCEPTIONS.replace("2027-01-01", "2030-01-01"), "more than one year"),
        (GOOD_EXCEPTIONS + GOOD_EXCEPTIONS, "duplicate"),
        ("exception = 5", "array"),
    ],
)
def test_register_validation(tmp_path: Path, text: str, message: str) -> None:
    reg = tmp_path / "r.toml"
    reg.write_text(text)
    with pytest.raises(exc_mod.ExceptionRegisterError, match=message):
        exc_mod.load(reg, TODAY)


def test_repository_register_is_valid() -> None:
    root = Path(__file__).resolve().parents[2]
    entries = exc_mod.load(root / "security/exceptions.toml")
    assert all(e.owner and e.compensating for e in entries)


def test_render_marks_blocked(setup: tuple[Path, Path]) -> None:
    ev, reg = setup
    (ev / "verify.json").unlink()
    assert "Release gate: BLOCKED" in gate.render(gate.evaluate(ev, reg, TODAY))


@pytest.mark.parametrize(
    ("file", "content", "control"),
    [
        ("coverage.json", '{"totals": {', "Coverage"),
        ("coverage.json", "{}", "Coverage"),
        ("junit.xml", "<testsuites><testsuite", "Unit tests"),
        ("verify.json", "[not json", "Image signature"),
    ],
)
def test_malformed_evidence_fails_that_control(
    setup: tuple[Path, Path], file: str, content: str, control: str
) -> None:
    ev, reg = setup
    (ev / file).write_text(content)
    results = gate.evaluate(ev, reg, TODAY)
    assert _status(results, control) == gate.FAIL
    assert gate.blocked(results)


def test_unparseable_register_fails_without_crashing(setup: tuple[Path, Path]) -> None:
    ev, reg = setup
    reg.write_text("[[exception]\nid = ")
    results = gate.evaluate(ev, reg, TODAY)
    assert _status(results, "Exception register") == gate.FAIL


def test_duplicate_vulnerability_counted_once(setup: tuple[Path, Path]) -> None:
    ev, reg = setup
    vuln = {"VulnerabilityID": "CVE-2099-9999", "PkgName": "libbar", "Severity": "HIGH"}
    (ev / "trivy-image.json").write_text(
        json.dumps({"Results": [{"Vulnerabilities": [vuln]}, {"Vulnerabilities": [vuln]}]})
    )
    detail = next(r.detail for r in gate.evaluate(ev, reg, TODAY) if r.control.startswith("Zero"))
    assert detail.startswith("1 unaccepted")
