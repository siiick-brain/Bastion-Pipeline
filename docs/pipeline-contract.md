# Pipeline contract

Every CI platform implements the same mandatory stages. Orchestration differs per platform. A platform that cannot run a stage must say so here with the reason, so no control is silently omitted.

## Stages

| # | Stage | Inputs | Mandatory checks | Fails when | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | Source validation | Commit range | Author and committer match `.github/allowed-author`. Conventional Commit title. No co-author or tool trailers. Style rules. | Any commit violates the policy | Job log of `scripts/check-authorship.sh`, `check-style.ps1` |
| 2 | Linting | Source | ruff lint and format, mypy strict, yamllint, actionlint, zizmor, shellcheck, hadolint, PSScriptAnalyzer | Any finding | Job log |
| 3 | Unit testing | Source, `app/requirements-dev.txt` | pytest, coverage at least 85 percent (line and branch), Pester | A failing test or coverage below 85 | `junit.xml`, `coverage.json`, `pester-results.xml` |
| 4 | Integration testing | Built image | `tests/integration -m integration` against the running container | Any runtime check fails | Job log |
| 5 | Security scanning | Source, image | Semgrep (ERROR severity), Gitleaks (full history), Trivy config, ZAP baseline | Any blocking finding | SARIF, ZAP report |
| 6 | Dependency analysis | Lock files | OSV-Scanner, dependency review on PRs | Any known vulnerability not in the exception register | Job log |
| 7 | Container construction | Dockerfile | hadolint, digest-pinned bases, Trivy image gate (critical and high) | Unaccepted critical or high finding | `trivy-image.json` |
| 8 | SBOM generation | Image digest | CycloneDX 1.6 and SPDX 2.3 from Syft, schema validation, digest binding | Invalid SBOM or SBOM for another digest | `sbom.cdx.json`, `sbom.spdx.json`, `sbom-check.json` |
| 9 | Artifact signing | Image digest, `SHA256SUMS` | Keyless cosign signatures | Signing fails | Rekor entries |
| 10 | Provenance generation | Image digest, zip | GitHub SLSA v1 build provenance | Attestation fails | Attestation in GHCR and GitHub |
| 11 | Artifact verification | Digest, tag, commit | Identity, issuer, SBOM attestations, provenance policy, checksum signature, negative controls | Any verification fails or a negative control passes | `verify.json` |
| 12 | Release approval | All evidence | `gate.py` in the `production` environment with a required reviewer | Any mandatory control is FAIL or NOT VERIFIED | `gate-summary.md` |
| 13 | Deployment | Verified digest | `promote.ps1` verifies before editing the overlay. ArgoCD syncs. | Verification fails | Git commit of the overlay |
| 14 | Deployment verification | Running cluster | `verify-deployment.ps1`: running digest, signature, UID, read-only root, capabilities, admission, sync, drift | Any check FAILs | `docs/deployment-verification.md` |

## Platform coverage

| Stage | GitHub Actions | GitLab CI | Jenkins |
| --- | --- | --- | --- |
| 1 Source validation | `ci.yml` policy | `policy` job | `Source validation` stage (authorship only; style needs PowerShell, which the agent does not have) |
| 2 Linting | `ci.yml`, `windows.yml` | `lint` job | `Lint` stage |
| 3 Unit testing | `_build-test.yml`, `windows.yml` | `test` job | `Unit tests and coverage gate` stage |
| 4 Integration testing | `ci.yml` container | NOT APPLICABLE: shared runners would need Docker-in-Docker with privileged mode, which this project avoids | NOT APPLICABLE: the agent has no container runtime by design (T4) |
| 5 Security scanning | `security.yml` | `semgrep`, `gitleaks`, `trivy` jobs | `Secret scan` stage (Gitleaks). Semgrep NOT APPLICABLE: kept to one SAST owner per platform with network access |
| 6 Dependency analysis | `security.yml` osv, dependency-review | `osv` job | `Dependency analysis` stage |
| 7 Container construction | `ci.yml`, `release.yml` | NOT APPLICABLE (same reason as stage 4) | NOT APPLICABLE (same reason as stage 4) |
| 8 SBOM generation | `release.yml` | `sbom` job (source SBOM) | NOT APPLICABLE: release artifacts are produced only by GitHub |
| 9 to 12 Signing, provenance, verification, approval | `release.yml` | NOT APPLICABLE: GitHub is the single release authority | NOT APPLICABLE: GitHub is the single release authority |
| 13, 14 Deployment | `promote.ps1`, ArgoCD, `verify-deployment.ps1` | NOT APPLICABLE | NOT APPLICABLE |

One release authority is a deliberate choice: two platforms signing the same artifact would need two trusted identities and double the verification policy. See [ADR 0001](adr/0001-keyless-signing.md).

## Shared scripts

`scripts/check-authorship.sh`, `scripts/lib/commit-policy.sh`, `app/requirements-dev.txt` (hash-locked tools), `pyproject.toml` (ruff, mypy, pytest and coverage settings) and `osv-scanner.toml` are used unchanged by all three platforms.
