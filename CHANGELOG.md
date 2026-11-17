# Changelog

## 0.2.1 (2026-11-17)

### Added

- The release gate records the SonarCloud quality gate of the released commit (`scripts/release/sonar_status.py`). The control is advisory and never blocks a release.
- Pester tests for `promote.ps1`.

### Fixed

- Gitleaks scanned every branch, so a pushed `gate-demo/fake-secret` branch would have failed the secrets gate on `main`. It now scans the history reachable from the checked-out commit.
- `promote.ps1` dropped the final newline of the overlay file, so every promotion failed yamllint. It also suggested a commit title the commit policy rejects.
- `promote.ps1` and `verify-deployment.ps1` find cosign under its winget name.
- The unpinned-action gate demo failed on yamllint before zizmor could run.
- The authorship check rejected the committer identity that GitHub records for web merges.

### Changed

- Chainguard Python base image digests updated.

## 0.2.0 (2026-11-16)

First signed release: image `sha256:706f6b48...` with SBOMs, provenance and a gated `production` approval.

### Fixed

- Tests could not run: the test client dependency was missing. Dependencies are now hash-locked and split into runtime and development sets.
- The hardened image built but did not start (Python 3.12 packages in a Python 3.11 runtime). Rebuilt on a matched Chainguard base with 0 known vulnerabilities.
- Windows CI passed an array to `Invoke-ScriptAnalyzer`. Analyzer and Pester failures now fail the build.
- The Trivy action tag did not exist. All actions are now pinned by commit SHA.
- Workflows triggered on `main` while the default branch was `master`. The branch is now `main`.
- `apply-branch-protection.ps1` did not parse and would have locked out the sole maintainer.
- The commit-msg hook accepted any title and was not executable on Linux or macOS.
- The ZAP rules file was not in ZAP format.
- A failed `state.json` write after activation left a device running the new version with an anti-rollback counter that still accepted older packages. The state now advances before `current` is switched.
- Malformed evidence files or a malformed exception register crashed the release gate without a summary. They now fail the affected control.
- The SBOM check printed a traceback instead of a FAIL result for some malformed SBOMs.

### Security

- Release workflow rebuilt: per-job permissions, push and sign by digest, SBOMs in two formats, provenance, identity verification, negative controls and a gate in the `production` environment.
- Removed `curl | sh` installers, `|| true` on security steps and a script that produced placeholder screenshot files.
- Input validation rejects control characters and unknown fields; responses carry security headers.
- Jenkins agent can no longer read the controller's secrets; the agent host key is pinned.
- Python dependencies install from wheels only, so no package setup script runs at install time.
- Jenkins controller configuration and the signing container code are root owned and read only for the runtime user; agent downloads are HTTPS only.
- The signing image copies an explicit file list, backed by a `.dockerignore` allowlist.
- Commits use the GitHub no-reply address; the authorship check accepts each listed identity.

### Added

- Architecture, threat model, pipeline contract, control matrix, tool ownership, operations, known limitations and five ADRs.
- OIDC verifier, provenance and SBOM policy checks, release gate, SoftHSM update signing, firmware simulation, kind deployment verification, Jenkins infrastructure.
