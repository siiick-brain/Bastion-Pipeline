# Screenshots

Screenshots must show real executions. None are committed yet, so every screenshot is NOT VERIFIED. Images go in `docs/images/`.

## Capture plan

| Image | Source | Status |
| --- | --- | --- |
| hardening-table, tests-green, cosign-verify, oidc-claims, softhsm-signing, firmware-sim, deployment-verification, secret-scan | Terminal output of the commands in each document | NOT VERIFIED |
| argocd-synced, argocd-drift-healed, jenkins-stages, zap-report, zap-juice-demo | Local web pages | NOT VERIFIED |
| actions-overview, ci-job-graph, code-scanning, sonarcloud-gate, gitleaks-blocked-pr, vuln-dependency-blocked-pr, release-assets, gitlab-pipeline, windows-job-log, oidc-denied, readme-top | Public GitHub and GitLab pages after hosted runs | NOT VERIFIED |
| branch-ruleset, production-approval | Manual, steps below | NOT VERIFIED |

## Manual: branch-ruleset

1. Run `pwsh -File scripts/apply-branch-protection.ps1 -Apply` and confirm. The script verifies the ruleset after applying it.
2. Open `https://github.com/siiick-brain/Bastion-Pipeline/settings/rules`.
3. Open the `main-protection` ruleset.
4. Capture the page showing enforcement "Active", the target branch and the rules list (deletion, force push, linear history, pull request, required status checks).
5. Save as `docs/images/branch-ruleset.png`.

## Manual: production-approval

1. Open `https://github.com/siiick-brain/Bastion-Pipeline/settings/environments` and create the environment `production`.
2. Enable "Required reviewers", add `siiick-brain`, enable "Prevent self-review" only if a second reviewer exists. Restrict deployment branches to tags matching `v*.*.*`.
3. Push a release tag. When the `release` run reaches the `gate` job, GitHub shows "Review deployments".
4. Capture the review dialog with the environment name and the pending job.
5. Approve, wait for the gate summary, then save the capture as `docs/images/production-approval.png`.
