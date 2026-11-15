# Known limitations

This project demonstrates secure delivery practices. It is not production ready and does not claim to be.

## Scope

- No cloud account. OIDC is verified locally; cloud federation is PLANNED.
- The only deployment target is a local kind cluster.
- The notes service stores data in memory and has no authentication. It exists to be delivered, not to be used. Each pod has its own store, so with the prod overlay's two replicas a note created through one pod returns 404 from the other.

## Not verified until hosted runs happen

All GitHub workflows were validated locally (actionlint, zizmor, yamllint) and their scripts were executed locally. The following need a push or a tag before they can be PASS: hosted CI runs, the release workflow, keyless signing of a Bastion artifact, the release gate, the `production` environment approval, the OIDC demo with a real token, the DAST demo workflow, scheduled scans, SonarCloud (needs `SONAR_TOKEN`), GitLab CI (needs a GitLab remote), ArgoCD sync and drift healing from GitHub, branch ruleset application and the gate demo pull requests.

## Security limits

| Area | Limit | Mitigation or plan |
| --- | --- | --- |
| Signature enforcement | Verified before promotion, not at admission. Cluster-admin can deploy an unsigned image. | Admission controller with a Sigstore policy (PLANNED) |
| Sigstore | Public Rekor log reveals repository and digests. Depends on public Sigstore availability. | Accepted for a public repository |
| SoftHSM | Software token, no hardware protection. The rollback counter is a file that an attacker with volume write access can reset. | Documented; a real HSM or TPM monotonic counter is required in production |
| Firmware | Simulation only. No hardware root of trust. | Documented as a simulation |
| Jenkins | Long-lived agent. Job DSL script security disabled for the seed script. | Ephemeral agents (PLANNED) |
| Local registry | `localhost:5001` is plain HTTP and local only. | Never exposed beyond 127.0.0.1 |
| Chainguard base | The free tier publishes only `latest`. Digest pinning keeps builds stable; Dependabot proposes updates. | ADR 0004 |
| Reproducible builds | Not claimed. No byte-for-byte comparison of independent builds. | PLANNED |
| Dependabot authorship | Dependabot commits are authored by `dependabot[bot]`, which conflicts with the sole-author policy. `check-authorship.sh` exempts them only on `dependabot/*` branches. | Owner decides whether to squash-merge under their own identity |
| Legacy commits | The two commits before the audit do not have Conventional Commit titles. History is not rewritten; CI checks only new commits. | Accepted |
| Windows | `build.bat` falls back to Windows PowerShell 5.1 when pwsh is absent; the Pester suite needs Pester 5 or later. | Prerequisite check fails clearly |

## Environment notes from the audit

- Docker Desktop stopped once during the session under load (kind, ArgoCD and other local containers). Restarting Docker Desktop restored the cluster.
- On Windows, Git Bash rewrites container paths unless `MSYS_NO_PATHCONV=1` is set. `scripts/zap-scan.sh` handles this.
