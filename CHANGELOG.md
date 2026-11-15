# Changelog

## Unreleased

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

### Added

- Architecture, threat model, pipeline contract, control matrix, tool ownership, operations, known limitations and five ADRs.
- OIDC verifier, provenance and SBOM policy checks, release gate, SoftHSM update signing, firmware simulation, kind deployment verification, Jenkins infrastructure.
