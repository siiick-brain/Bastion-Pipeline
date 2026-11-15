"""Policy tests against a real `gh attestation verify --format json` result (trimmed).

Fixture: GitHub CLI v2.104.0 release, captured 2026-11-15 with
`gh attestation verify gh_2.104.0_linux_arm64.tar.gz --repo cli/cli --format json`.
Each negative case mutates one claim, simulating a valid signature over the wrong thing.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from scripts.release.verify_provenance import Policy, ProvenanceError, main, verify

FIXTURE = Path(__file__).resolve().parents[2] / "tests/fixtures/gh-attestation-verify-cli.json"
GOOD = Policy(
    digest="sha256:cb34cefc6f4e77b90731374a2b737516bb8f3033c6ca46aa949e5344f68069e3",
    repo="cli/cli",
    ref="refs/heads/trunk",
    commit="3d5a9e355a837f2f5ee78d7484c118cc1342ad1a",
    workflow=".github/workflows/deployment.yml",
)
CLI_ARGS = [
    "--digest",
    GOOD.digest,
    "--repo",
    GOOD.repo,
    "--ref",
    GOOD.ref,
    "--commit",
    GOOD.commit,
    "--workflow",
    GOOD.workflow,
]


def _load() -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return data


def _cert(d: list[dict[str, Any]]) -> dict[str, Any]:
    cert: dict[str, Any] = d[0]["verificationResult"]["signature"]["certificate"]
    return cert


def _stmt(d: list[dict[str, Any]]) -> dict[str, Any]:
    stmt: dict[str, Any] = d[0]["verificationResult"]["statement"]
    return stmt


def test_real_attestation_satisfies_policy() -> None:
    assert verify(_load(), GOOD) == 1


@pytest.mark.parametrize(
    ("label", "policy"),
    [
        (
            "modified artifact / incorrect digest",
            Policy(**{**GOOD.__dict__, "digest": "sha256:" + "0" * 64}),
        ),
        ("wrong repository", Policy(**{**GOOD.__dict__, "repo": "attacker/cli"})),
        ("incorrect source revision", Policy(**{**GOOD.__dict__, "commit": "f" * 40})),
        ("wrong ref", Policy(**{**GOOD.__dict__, "ref": "refs/tags/v9.9.9"})),
        (
            "wrong signing workflow",
            Policy(**{**GOOD.__dict__, "workflow": ".github/workflows/ci.yml"}),
        ),
    ],
)
def test_policy_mismatch_is_rejected(label: str, policy: Policy) -> None:
    with pytest.raises(ProvenanceError):
        verify(_load(), policy)


Mutation = Callable[[list[dict[str, Any]]], None]
MUTATIONS: dict[str, Mutation] = {
    "wrong certificate issuer": lambda d: _cert(d).update(issuer="https://accounts.google.com"),
    "wrong signing identity": lambda d: _cert(d).update(
        subjectAlternativeName="https://github.com/cli/cli/.github/workflows/evil.yml@refs/heads/trunk"
    ),
    "self-hosted runner": lambda d: _cert(d).update(runnerEnvironment="self-hosted"),
    "modified provenance subject": lambda d: _stmt(d)["subject"][8]["digest"].update(
        sha256="1" * 64
    ),
    "unexpected artifact only": lambda d: _stmt(d).update(
        subject=[{"name": "other.bin", "digest": {"sha256": "2" * 64}}]
    ),
    "wrong predicate type": lambda d: _stmt(d).update(predicateType="https://example.com/fake"),
    "modified builder id": lambda d: _stmt(d)["predicate"]["runDetails"]["builder"].update(
        id="https://evil.example/builder"
    ),
    "modified provenance commit": lambda d: _stmt(d)["predicate"]["buildDefinition"][
        "resolvedDependencies"
    ][0]["digest"].update(gitCommit="e" * 40),
    "modified predicate ref": lambda d: _stmt(d)["predicate"]["buildDefinition"][
        "externalParameters"
    ]["workflow"].update(ref="refs/heads/feature"),
    "missing certificate": lambda d: d[0]["verificationResult"].pop("signature"),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_tampered_attestation_is_rejected(name: str) -> None:
    data = copy.deepcopy(_load())
    MUTATIONS[name](data)
    with pytest.raises(ProvenanceError):
        verify(data, GOOD)


@pytest.mark.parametrize("data", [[], {}, None, [{"no": "result"}]])
def test_missing_provenance_is_rejected(data: object) -> None:
    with pytest.raises(ProvenanceError):
        verify(data, GOOD)


def test_cli_pass_and_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(FIXTURE), *CLI_ARGS]) == 0
    assert '"status": "PASS"' in capsys.readouterr().out
    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    assert main([str(bad), *CLI_ARGS]) == 1
    assert main([str(tmp_path / "missing.json"), *CLI_ARGS]) == 1
