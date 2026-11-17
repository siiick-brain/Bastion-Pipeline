# ADR 0003: GitOps promotion by verified digest

Date: 2026-11-15. Status: Accepted.

## Context

Deployment must use exactly the artifact that was signed and verified. Tags are mutable, so a deploy by tag can run different bytes than were verified.

## Decision

- Overlays reference `image@sha256:<digest>` only. The committed placeholder digest is all zeros, so nothing runs until a digest is promoted.
- `scripts/promote.ps1` verifies the signature (exact identity and issuer) before it edits the overlay. It refuses tags. It prints the diff and never commits: the owner commits.
- ArgoCD applies the committed state with automated sync, prune and self-heal.
- `scripts/verify-deployment.ps1` compares the running pod's image digest with the overlay digest and checks the effective security context from inside the pod.

## Consequences

- Verification happens before promotion, not at admission. A user with cluster-admin can still apply an unsigned image directly. Admission-time verification was added later in [ADR 0006](0006-admission-signature-policy.md).
- Rollback is a `git revert` of the promotion commit.
