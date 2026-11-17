# Tool ownership

Every tool has one job. "Gate" means a failure blocks a pull request or a release. Versions are the pinned versions on 2026-11-15. Overlap is deliberate only where noted ([ADR 0002](adr/0002-scanner-split.md)).

| Tool | Version | Purpose | Input | Output | Gate | Schedule | Overlaps with | Sends data to | Limitations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ruff | 0.17.5 | Lint and format | Python | Findings | PR | | | | Style and common bugs only |
| mypy | 2.4.1 | Static types (strict) | Python | Findings | PR | | | | Untyped third-party code is opaque |
| pytest, pytest-cov, hypothesis | 9.2.0, 7.1.0, 6.170.15 | Tests, coverage gate 85, property tests | Python | `junit.xml`, `coverage.json` | PR, release | | | | Coverage does not prove test quality |
| PSScriptAnalyzer | 1.25.0 | PowerShell lint | `.ps1` | Findings | PR (Windows) | | | | |
| Pester | 6.2.0 | PowerShell tests | `.tests.ps1` | NUnit XML | PR (Windows) | | | | |
| yamllint | 1.38.0 | YAML syntax and style | YAML | Findings | PR | | actionlint (partly) | | |
| actionlint | 1.7.12 | Workflow semantics, embedded shellcheck | Workflows | Findings | PR | | yamllint | | |
| zizmor | 1.32.0 | Workflow security (permissions, injection, pinning) | Workflows | Findings | PR | | | | Configured in `.github/zizmor.yml` |
| shellcheck | runner default | Shell lint | `.sh`, hook | Findings | PR | | | | |
| hadolint | 2.14.0 | Dockerfile lint | Dockerfiles | Findings | PR | | Trivy config | | |
| kubeconform | 0.7.0 | Kubernetes schema validation | Rendered overlays | Findings | PR | | | | Schemas only, no policy |
| Semgrep | 1.140.0 | SAST | Source | SARIF to code scanning | PR (ERROR severity) | | SonarCloud | Rule registry download | Rule packs `p/python`, `p/dockerfile`, `p/github-actions`, `p/secrets` |
| SonarCloud | scan action 8.4.1 | Quality gate, second SAST opinion | Source | Quality gate status | Advisory (gate wait when configured) | | Semgrep | sonarcloud.io (source code) | NOT VERIFIED until `SONAR_TOKEN` is configured |
| Gitleaks | 8.30.1 | Secrets in full history | Git history | Findings | PR | | Trivy secret scanner | | Pattern based |
| OSV-Scanner | 2.2.4 | Known vulnerabilities in lock files | Lock files | Findings | PR | Weekly full scan | Dependency-Check, Trivy | osv.dev (package names) | Exceptions only through `osv-scanner.toml` plus the register |
| dependency-review-action | 5.0.0 | New vulnerable or GPL dependencies in a PR | PR diff | Findings | PR | | OSV-Scanner | GitHub | PRs only |
| Trivy | 0.76.2 | Image vulnerabilities, IaC misconfiguration | Image, repo | Table, JSON | PR, release | | OSV, hadolint | Vulnerability DB download | Ignore file entries expire |
| OWASP Dependency-Check | image digest pinned | Deep CVE scan | `app/` | HTML, JSON | No (scheduled) | Weekly | OSV-Scanner | NVD | Slow, needs NVD key for rate limits |
| ZAP | stable, digest pinned | DAST | Local container only | HTML, JSON | PR (baseline) | Weekly (full) | | | `scripts/zap-scan.sh` refuses non-local targets |
| Syft | 1.55.0 | SBOMs | Image digest | CycloneDX 1.6, SPDX 2.3 | Release | | | Registry pull | |
| cyclonedx-cli | 0.29.1 | CycloneDX schema validation | SBOM | Pass or fail | Release | | | | Supports up to CycloneDX 1.6 |
| spdx-tools (pyspdxtools) | 0.8.5 | SPDX validation | SBOM | Pass or fail | Release | | | | |
| cosign | 3.1.4 | Keyless signing and verification | Digest, blobs | Signatures, attestations | Release | | | Sigstore Fulcio and Rekor (public log) | |
| GitHub artifact attestations | attest-build-provenance 4.2.2 | SLSA v1 provenance | Digest, zip | Attestation | Release | | | GitHub, Sigstore | |
| kind, kubectl, kustomize | 0.33.0, 1.36.1, 5.8.1 | Local cluster and rendering | Overlays | Running cluster | Deployment | | | | Local only |
| ArgoCD | 3.6.1 | GitOps sync and self-heal | GitHub repository | Sync status | Deployment | | | github.com (pull) | Admission-time signature policy by Kyverno (opt-in) |
| SoftHSM2, python-pkcs11 | Debian 13 package, 0.10.1 | PKCS#11 signing | Manifest | Signature | Container job | | | | Software token, not an HSM |
| Dependabot | GitHub | Update PRs with 7-day cooldown | Manifests | PRs | | Weekly | | GitHub | |

## Update procedure

1. Dependabot opens a pull request after the 7-day cooldown.
2. For Python, regenerate the lock with the command in the header of the matching `.in` file.
3. For actions, keep the full commit SHA and update the version comment.
4. For images, update the digest and the tag comment.
5. All PR gates must pass. Vulnerability exceptions go through `security/exceptions.toml` (reason, risk, owner, expiry at most one year ahead).
