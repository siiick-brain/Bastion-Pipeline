# ADR 0006: Admission-time signature enforcement with Kyverno

Date: 2026-11-17. Status: Accepted. Extends [ADR 0003](0003-gitops-promotion.md).

## Context

`promote.ps1` verifies the release signature before a digest is committed to an overlay, and ArgoCD deploys only what Git holds. Nothing stopped a user with cluster access from applying an unsigned image to the `bastion` namespace directly.

## Decision

- Kyverno v1.19.2, installed by `scripts/kind-up.ps1 -WithAdmission` from a manifest pinned by SHA-256 in `infra/kyverno/versions.env`.
- `infra/kyverno/require-signed-images.yaml` holds two policies on the current `policies.kyverno.io/v1` API (the older `ClusterPolicy` kind is deprecated):
  - `ValidatingPolicy` `bastion-project-image-by-digest`: every container in the `bastion` namespace must be `ghcr.io/siiick-brain/bastion-pipeline@sha256:...`.
  - `ImageValidatingPolicy` `bastion-release-signature`: that image must carry a keyless signature from `release.yml` on a `vX.Y.Z` tag, issued by GitHub Actions and logged in Rekor. This is the identity that `docs/verify.md` and `promote.ps1` check.
- Both policies deny and fail closed: when Kyverno is unavailable, new pods in `bastion` are not admitted.

## Consequences

- `scripts/verify-admission.ps1` sends five pods through admission with a server-side dry run. The two signed releases are admitted. A tag reference, an image from another registry and an unsigned object from the project repository are rejected.
- `scripts/kind-demo.ps1` signs with a local key and deploys from `localhost:5001`, so it cannot run on a cluster set up with `-WithAdmission`.
- Cluster-admin can still remove the policies or Kyverno itself. Admission control raises the bar for a namespace user, not for a cluster administrator.
- v1.19.2 signs only its checksums file, which does not cover `install.yaml`, so the manifest is pinned by hash only. Releases from v1.20.0 sign `install.yaml`; after the seven-day adoption delay the pin can move to a signature-verified manifest.
