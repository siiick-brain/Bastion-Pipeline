# Control matrix

Requirement, implementation, test, evidence and status. Status words are defined in [the glossary](GLOSSARY.md). Local evidence was produced on 2026-11-15 on Windows 11 with Docker Desktop 29.9. "Hosted" means a GitHub, GitLab or release run. The first hosted GitHub runs passed on 2026-11-16 for commit `bdfb847`; release, GitLab and ArgoCD runs have not happened yet.

## Source and build

| ID | Requirement | Implementation | Test | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| C01 | Sole author, no co-author or tool attribution trailers, Conventional titles | `scripts/hooks/commit-msg`, `scripts/lib/commit-policy.sh`, `.github/allowed-author` | `tests/test_commit_policy.py` (19) | `pytest tests` | PASS |
| C02 | Same policy in CI on new commits | `scripts/check-authorship.sh` in `ci.yml`, GitLab `policy`, Jenkins stage 1 | Jenkins build 9; GitHub `ci` run 43815627919 | `run_job.py` output; `policy` job | PASS (Jenkins, hosted) |
| C03 | Style rules enforced | `scripts/check-style.ps1`, `.style-allow` | `tests/style/check-style.tests.ps1` (6) | Pester 6.2.0 | PASS |
| C04 | Dependencies hash-locked, runtime separated | `app/requirements*.txt`, `update-signing/requirements.txt` | `test_no_dev_tools_in_image` | `pytest tests/integration -m integration` | PASS |
| C05 | Lint: ruff, mypy strict, yamllint, actionlint, zizmor, shellcheck, hadolint | `ci.yml` policy, `_build-test.yml` | `validate-pipeline.ps1` | local run; GitHub `ci` run 43815627919 | PASS (local, hosted) |
| C06 | Tests with coverage at least 85 | `pyproject.toml` `fail_under = 85` | 237 tests | `pytest --cov`: 93.76 percent | PASS |
| C07 | Security-critical behaviour has negative tests | OIDC, provenance, gate, SBOM, update, firmware, hook, Windows suites | see each row below | | PASS |

## App and container

| ID | Requirement | Implementation | Test | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| C10 | Strict input validation | `app/main.py` (lengths, control characters, unknown fields, ID range, store limit) | `app/test_main.py` (49, includes Hypothesis) | `pytest app` | PASS |
| C11 | Security headers, no docs endpoints | middleware in `app/main.py` | `test_security_headers_on_every_response`, `test_interactive_docs_are_disabled` | `pytest app` | PASS |
| C12 | Image starts and serves | `Dockerfile` | `tests/integration/test_container.py` | 11 runtime tests | PASS |
| C13 | Non-root, no shell, read-only root, no capabilities | `Dockerfile`, runtime flags | same suite | `/proc/1/status` from the running process | PASS |
| C14 | Zero unaccepted critical or high in the image | Chainguard base, Trivy gate | `trivy image --severity CRITICAL,HIGH --exit-code 1` | 0 findings | PASS |
| C15 | Before and after comparison from real scans | `Dockerfile.naive` | Trivy 0.76.2 | [hardening](hardening.md) | PASS |

## Windows

| ID | Requirement | Implementation | Test | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| C20 | Analyzer and Pester failures fail the build | `windows/build.ps1` | build run | PSScriptAnalyzer reports, Pester result check | PASS (local) |
| C21 | Paths with spaces, unrelated working directory | `BastionBuild.psm1` | `windows/tests/build.tests.ps1` | Pester 31 tests | PASS |
| C22 | Missing prerequisites and inputs fail clearly | same | same | same | PASS |
| C23 | Interrupted packaging leaves no partial package, temp cleaned | atomic `.partial` rename, `finally` cleanup | same | same | PASS |
| C24 | Checksum format and tamper detection, path traversal refused | `Write-Checksum`, `Test-Checksum` | same | same | PASS |
| C25 | `build.bat` propagates exit codes without admin | `windows/build.bat` | Pester and `windows.yml` | Pester; GitHub `windows` run 43815627895 | PASS (local, hosted) |

## CI security

| ID | Requirement | Implementation | Test | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| C30 | Minimal permissions per job | `permissions: {}` at workflow level | zizmor | no findings | PASS (static) |
| C31 | Actions pinned by full SHA, 7-day cooldown | all workflows, `dependabot.yml` | zizmor `unpinned-uses` | no findings | PASS (static) |
| C32 | Timeouts, concurrency, retention | all workflows | actionlint | | PASS (static) |
| C33 | Safe fork PRs, no `pull_request_target`, no secrets | `ci.yml`, `security.yml` | zizmor | | PASS (static), NOT VERIFIED (hosted fork PR) |
| C34 | Release permissions only in release jobs and tag refs | `release.yml` | zizmor, review | | PASS (static) |

## Security scanning

| ID | Requirement | Implementation | Test | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| C40 | SAST | Semgrep (gate), SonarCloud (advisory) | hosted | GitHub `security` runs 43815627776 (Semgrep) and 43933855306 (SonarCloud quality gate: security, reliability and maintainability A, 0 vulnerabilities, coverage 94.1 percent) | PASS |
| C41 | Secrets | Gitleaks | `gitleaks git .` | no leaks in history | PASS (local) |
| C42 | SCA | OSV-Scanner gate, dependency review, Dependency-Check weekly | `osv-scanner` on locks | no issues; jinja2 2.10 demo flagged | PASS (local) |
| C43 | IaC | Trivy config, kubeconform | `trivy fs --scanners misconfig` | | PASS (local) |
| C44 | DAST baseline on own app only | `scripts/zap-scan.sh` with scope guard | local ZAP run | see [DAST demo](dast-demo.md) | see DAST demo |
| C45 | Exceptions have reason, risk, owner, expiry | `security/exceptions.toml`, `gate.py` | `test_register_validation` | | PASS |

## Supply chain and release

| ID | Requirement | Implementation | Test | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| C50 | SBOMs in both formats bound to the digest | Syft, `sbom_check.py` | `test_sbom_check.py` (12), real Syft output | cyclonedx-cli and pyspdxtools pass, corrupted copies fail | PASS (local) |
| C51 | Keyless signing by digest | `release.yml` build job | hosted | GitHub release run 43983071969; independent `cosign verify` of `v0.2.0` | PASS |
| C52 | Identity and issuer verification | `verify-release.sh` | `test_supply_chain.py` (real Sigstore) | 5 identity cases | PASS (local) |
| C53 | Provenance subject, workflow, ref, commit, runner | `verify_provenance.py` | `test_verify_provenance.py` (21, real attestation) | | PASS |
| C54 | Tampered artifact fails | `verify-release.sh` negative controls | `test_modified_blob_fails_signature` | | PASS (local) |
| C55 | Release gate blocks on FAIL or NOT VERIFIED | `gate.py` | `test_gate.py` (26) | | PASS |
| C56 | Required reviewer on production | environment `production` | manual | GitHub release run 43983071969: gate waited until the owner approved | PASS |
| C57 | Branch ruleset with dry run, confirmation, verification | `apply-branch-protection.ps1` | dry run, then `-Apply` against the real repository | 2026-11-17: ruleset 27441845 `main-protection` active on `refs/heads/main` (deletion, non fast forward, linear history, pull request, 9 required checks) | PASS |

## OIDC

| ID | Requirement | Implementation | Test | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| C60 | Algorithm allowlist, JWKS by kid, rotation, claims, policy, masking | `scripts/oidc/verifier.py` | `scripts/oidc/test_verifier.py` (44) | | PASS |
| C61 | Real JWKS reachable and validated | same | `test_oidc_live.py` | | PASS |
| C62 | Real token accepted on main, denied elsewhere | `oidc-demo.yml` | hosted | GitHub `oidc-demo` runs 43815627785 (ACCEPTED on main, wrong audience REJECTED) and 44045166737 (REJECTED: ref `refs/heads/gate-demo/failing-test` not allowed by policy) | PASS |

## Deployment

| ID | Requirement | Implementation | Test | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| C70 | Promotion only of verified digests | `promote.ps1` | `kind-demo.ps1` (unsigned refused, signed promoted) | [deployment verification](deployment-verification.md) | PASS (local key) |
| C71 | Running digest equals signed digest | `verify-deployment.ps1` | kind | same | PASS |
| C72 | Effective pod security context | same | kind | same | PASS |
| C73 | Admission rejects privileged pods | Pod Security `restricted` | kind dry run | same | PASS |
| C74 | ArgoCD Synced, Healthy, drift healed, rollback | `infra/argocd` | `verify-deployment.ps1` on kind | 2026-11-17: Synced and Healthy at commit `87fb5bc` from GitHub, scaled to 3 and restored to 1 (see [deployment verification](deployment-verification.md)) | PASS (sync, drift), NOT VERIFIED (rollback needs a second release) |
| C75 | No public exposure | ClusterIP, 127.0.0.1 binds, NetworkPolicy | manifest review | | PASS (static) |

## Jenkins and GitLab

| ID | Requirement | Implementation | Test | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| C80 | Jenkins runs the contract source stages | `Jenkinsfile`, `infra/jenkins` | build 9 | [Jenkins](jenkins.md) | PASS |
| C81 | No Docker socket, isolated agent, secrets masked, host key pinned | `compose.yaml`, `casc.yaml` | `docker inspect`, `docker exec` | [Jenkins](jenkins.md) | PASS |
| C82 | GitLab CI valid | `.gitlab-ci.yml` | JSON schema | | PASS (schema), NOT VERIFIED (run) |

## Signed updates and firmware

| ID | Requirement | Implementation | Test | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| C90 | Non-extractable P-256 key on a token, per-run PIN | `init-token.sh`, `pkcs11_signer.py` | `test_pkcs11.py` in the container | | PASS |
| C91 | Verification fails closed on every negative case | `device.py` | `test_update.py` (50) | | PASS |
| C92 | Anti-rollback persists across container restarts | `state.json` on a volume | two container runs | | PASS |
| C93 | Atomic install, interrupted install recoverable | staging plus `os.replace` | `test_interrupted_install_leaves_previous_version` | | PASS |
| C94 | Firmware simulation accepts one image, rejects five | `boot_sim.py` | `test_boot_sim.py` (20) | | PASS |

## Evidence and hygiene

| ID | Requirement | Implementation | Test | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| C100 | No fabricated evidence | `screenshot-prep.ps1` (wrote fake PNGs) removed | review | | PASS |
| C101 | No secrets committed | Gitleaks | history scan | | PASS |
| C102 | Fresh-clone reproduction | `operations.md` first setup | clean clone, new virtual environment, `validate-pipeline.ps1` | 2026-11-17, commit `6ddf9ee`: 17 of 17 checks PASS (clone of the local repository; a clone from GitHub follows the push) | PASS |
| C103 | Screenshots of real runs | `docs/screenshots.md` | headless browser capture of public pages | 2026-11-17: release job graph with the production approval, release assets, Actions overview | PASS (3 images), NOT VERIFIED (remaining plan) |
