"""Policy check on the output of `gh attestation verify --format json`.

`gh attestation verify` checks the Sigstore signature, certificate chain and transparency log.
This module then checks the claims inside the verified result, so that a valid signature from
the wrong workflow, ref, commit or artifact is still rejected:

* what was signed: the in-toto subject digest equals the expected artifact digest
* who signed it: certificate issuer and signer workflow identity
* how it was built: SLSA v1 predicate, builder id, source repository, ref and commit,
  GitHub-hosted runner

Usage:
  python -m scripts.release.verify_provenance <gh-verify.json> --digest sha256:... \
      --repo owner/name --ref refs/tags/v1.2.3 --commit <sha> \
      [--workflow .github/workflows/release.yml]
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GITHUB_ISSUER = "https://token.actions.githubusercontent.com"
SLSA_V1 = "https://slsa.dev/provenance/v1"
IN_TOTO_V1 = "https://in-toto.io/Statement/v1"


class ProvenanceError(ValueError):
    """The attestation does not satisfy the policy."""


@dataclass(frozen=True)
class Policy:
    digest: str
    repo: str
    ref: str
    commit: str
    workflow: str = ".github/workflows/release.yml"

    @property
    def signer_uri(self) -> str:
        return f"https://github.com/{self.repo}/{self.workflow}@{self.ref}"


def _expect(actual: object, expected: object, what: str) -> None:
    if actual != expected:
        raise ProvenanceError(f"{what}: expected {expected!r}, got {actual!r}")


def check_result(result: dict[str, Any], policy: Policy) -> None:
    vr = result.get("verificationResult")
    if not isinstance(vr, dict):
        raise ProvenanceError("missing verificationResult")
    cert = vr.get("signature", {}).get("certificate") or {}
    statement = vr.get("statement") or {}

    _expect(cert.get("issuer"), GITHUB_ISSUER, "certificate OIDC issuer")
    _expect(cert.get("subjectAlternativeName"), policy.signer_uri, "certificate identity")
    _expect(cert.get("buildSignerURI"), policy.signer_uri, "build signer URI")
    _expect(cert.get("sourceRepositoryURI"), f"https://github.com/{policy.repo}", "source repo")
    _expect(cert.get("sourceRepositoryRef"), policy.ref, "source ref")
    _expect(cert.get("sourceRepositoryDigest"), policy.commit, "source revision")
    _expect(cert.get("runnerEnvironment"), "github-hosted", "runner environment")

    _expect(statement.get("_type"), IN_TOTO_V1, "statement type")
    _expect(statement.get("predicateType"), SLSA_V1, "predicate type")
    algo, _, hexdigest = policy.digest.partition(":")
    subjects = statement.get("subject") or []
    if not any(s.get("digest", {}).get(algo) == hexdigest for s in subjects):
        raise ProvenanceError(f"no subject with digest {policy.digest}")

    predicate = statement.get("predicate") or {}
    build = predicate.get("buildDefinition") or {}
    workflow = build.get("externalParameters", {}).get("workflow", {})
    _expect(workflow.get("repository"), f"https://github.com/{policy.repo}", "predicate repo")
    _expect(workflow.get("ref"), policy.ref, "predicate ref")
    _expect(workflow.get("path"), policy.workflow, "predicate workflow path")
    commits = [
        d.get("digest", {}).get("gitCommit") for d in build.get("resolvedDependencies") or []
    ]
    if policy.commit not in commits:
        raise ProvenanceError("predicate resolvedDependencies does not contain the source commit")
    builder = predicate.get("runDetails", {}).get("builder", {}).get("id")
    _expect(builder, policy.signer_uri, "builder id")


def verify(results: object, policy: Policy) -> int:
    """Returns the number of results that satisfy the policy. Raises if none do."""
    if not isinstance(results, list) or not results:
        raise ProvenanceError("no attestations found (missing provenance)")
    errors: list[str] = []
    ok = 0
    for r in results:
        try:
            check_result(r, policy)
            ok += 1
        except ProvenanceError as exc:
            errors.append(str(exc))
    if ok == 0:
        raise ProvenanceError("; ".join(errors))
    return ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("results", type=Path)
    ap.add_argument("--digest", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--workflow", default=".github/workflows/release.yml")
    args = ap.parse_args(argv)
    policy = Policy(args.digest, args.repo, args.ref, args.commit, args.workflow)
    try:
        n = verify(json.loads(args.results.read_text(encoding="utf-8")), policy)
    except (ProvenanceError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}))
        return 1
    print(json.dumps({"status": "PASS", "matching_attestations": n, "signer": policy.signer_uri}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
