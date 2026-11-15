# Skills evidence

Date: 2026-11-15. Command: `pwsh -File scripts/verify-skills.ps1`.

Summary: NOT VERIFIED: 5, PASS: 16.

| # | Gate | Status | Evidence |
| --- | --- | --- | --- |
| 1 | GitHub Actions pipelines valid (local static checks) | PASS | `actionlint; zizmor`: No findings to report. Good job! (15 suppressed) |
| 2 | GitLab CI file validates (schema) | PASS | `check-jsonschema vendor.gitlab-ci`: ok -- validation done |
| 3 | Jenkinsfile runs locally | PASS | local Jenkins build 9: SUCCESS |
| 4 | PowerShell and batch jobs pass Pester, exit codes propagate | PASS | Invoke-Pester: passed 37 failed 0 |
| 5 | Linting and tests with coverage gate | PASS | `ruff; pytest --cov-fail-under=85`: Required test coverage of 85% reached. Total coverage: 93.74% |
| 6 | SAST: Semgrep and SonarCloud | NOT VERIFIED | Semgrep runs in security.yml (hosted run pending); SonarCloud needs SONAR_TOKEN |
| 7 | SCA: Dependabot config, OSV and Dependency-Check | NOT VERIFIED | dependabot.yml present: True; OSV: No issues found; Dependency-Check is scheduled (hosted run pending) |
| 8 | DAST: ZAP baseline and Juice Shop demo | PASS | local runs: app baseline 0 warnings (docs/dast-demo.md); Juice Shop 6 alert types |
| 9 | Gitleaks catches the demo secret | PASS | gitleaks dir on a random fake API key: detected True |
| 10 | Trivy image scan with before and after table | PASS | table in docs/hardening.md: True; gate on bastion-pipeline:local passed: True |
| 11 | SBOMs valid in both formats | NOT VERIFIED | validators and digest binding pass on real Syft output (docs/verify.md); release SBOMs need a tag |
| 12 | Hardened image runs non-root | PASS | `pytest tests/integration -m integration`: ...........                                                              [100%] |
| 13 | OIDC verifier accepts valid and rejects bad tokens | PASS | `pytest scripts/oidc`: ............................................                             [100%] |
| 14 | ArgoCD Synced and Healthy, drift healed | NOT VERIFIED | Application bastion-dev not present (needs pushed overlay and release) |
| 15 | Release gates block a failing condition | PASS | `pytest scripts/release/test_gate.py`: ................................                                         [100%] |
| 16 | cosign verify passes and a tampered artifact fails | PASS | `pytest tests/integration/test_supply_chain.py -m network`: ......                                                                   [100%] |
| 17 | SoftHSM signing, verification and negative cases | PASS | `docker run bastion-update-signing:local`: 55 passed, 1 skipped in 7.97s |
| 18 | Firmware simulation accepts one image and rejects five | PASS | `pytest firmware-sim`: ....................                                                     [100%] |
| 19 | Hygiene: authors, trailers, tooling files, gitleaks, style | PASS | authorship since baseline, gitleaks history, style: Style check passed. |
| 20 | Agent evidence files exist (private) | PASS | all present, gitignored |
| 21 | Images present and linked | NOT VERIFIED | 0 images in docs/images (capture plan in docs/screenshots.md) |
