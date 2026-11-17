# Known limitations

This project demonstrates secure delivery practices. It is not production ready and does not claim to be.

## Scope

- No cloud account. OIDC is verified locally; cloud federation is PLANNED.
- The only deployment target is a local kind cluster.
- The notes service stores data in memory and has no authentication. It exists to be delivered, not to be used. Each pod has its own store, so with the prod overlay's two replicas a note created through one pod returns 404 from the other.

## Not verified until hosted runs happen

The `ci`, `security`, `windows` and `oidc-demo` workflows passed on GitHub on 2026-11-16 (commit `bdfb847`). Release `v0.2.0` passed on 2026-11-16 (GitHub release run 43983071969): keyless signing, SBOM and provenance attestations, the release gate and the `production` approval. On 2026-11-17 the OIDC denial from a non-main ref, ArgoCD sync and drift healing from GitHub, the branch ruleset and the five gate demo pull requests passed as well. Release `v0.2.1`, its promotion, the rollback to `v0.2.0` and the hosted DAST demo passed later the same day. Still NOT VERIFIED: the scheduled scans (first weekly run pending), GitLab CI (needs a GitLab remote) and a pull request from a fork.

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
