# Release gates

The `gate` job in `.github/workflows/release.yml` runs `python -m scripts.release.gate evidence` in the `production` environment. A required reviewer must approve the job before it starts. The gate blocks when any mandatory control is FAIL or NOT VERIFIED.

| Control | Mandatory | Evidence file | Passes when |
| --- | --- | --- | --- |
| Exception register valid | yes | `security/exceptions.toml` | Every entry has reason, risk, owner and an expiry that is not past and at most one year ahead |
| Unit tests pass | yes | `junit.xml` | At least one test ran and none failed or errored |
| Coverage at least 85 percent | yes | `coverage.json` | Total line and branch coverage at least 85 |
| Zero unaccepted critical or high vulnerabilities | yes | `trivy-image.json` | Every critical or high finding is covered by an unexpired register entry |
| SBOMs describe the release digest | yes | `sbom-check.json` | Both SBOMs reference the digest and are not empty |
| CycloneDX schema valid | yes | `cdx-schema.txt` | cyclonedx-cli and pyspdxtools both pass |
| Image signature, identity and issuer verified | yes | `verify.json` | `cosign verify` with the exact release identity |
| Provenance verified | yes | `verify.json` | `gh attestation verify` plus `verify_provenance.py` |
| SBOM attestations verified | yes | `verify.json` | Both attestation types verify |
| Windows checksums signature verified | yes | `verify.json` | `cosign verify-blob` and `sha256sum -c` |
| Tampered artifact rejected | yes | `verify.json` | Tampered blob, wrong identity and wrong issuer all fail |
| SonarCloud quality gate | no | `sonarcloud.txt` | Reported, never blocks |

## Evidence

| Check | Command | Date | Result |
| --- | --- | --- | --- |
| Gate allows complete passing evidence and blocks every failing or missing control | `pytest scripts/release/test_gate.py` | 2026-11-15 | PASS, 26 tests |
| Gate in a hosted release | release workflow | | NOT VERIFIED (no tag pushed) |
| `production` environment with a required reviewer | repository settings | | NOT VERIFIED: manual setting, steps in [screenshots](screenshots.md) |

## Branch protection

`scripts/apply-branch-protection.ps1` manages a `main` ruleset: block deletion and force pushes, require pull requests (0 approvals so a sole maintainer is not locked out), linear history, resolved conversations and the required status checks. It is a dry run by default. With `-Apply` it asks for confirmation, applies the ruleset and reads it back to verify every rule. Dry run on 2026-11-15: PASS (no ruleset exists yet). Apply: NOT VERIFIED (needs the owner's decision).
