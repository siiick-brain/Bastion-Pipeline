# Deployment verification

Date: 2026-11-15. Command: `pwsh -File scripts/verify-deployment.ps1 -Overlay local`.

Overlay: `local`. Image: `localhost:5001/bastion-pipeline@sha256:030bad5d18c3eef96d2ead338cc5c651ed64f1981750413ec837dd2c5fe1dc43`.

| Check | Status | Evidence |
| --- | --- | --- |
| Running digest equals signed digest | PASS | pod bastion-notes-656df8468f-jx5tg imageID ends sha256:030bad5d18c3... |
| cosign verify passes | PASS | localhost:5001/bastion-pipeline@sha256:030bad5d18c3eef96d2ead338cc5c651ed64f1981750413ec837dd2c5fe1dc43 |
| Process runs as UID 65532 (non-root) | PASS | from /proc/1/status in the pod |
| Root filesystem is read-only | PASS | write to /srv/app returned EROFS |
| No capabilities, no privilege escalation | PASS | CapEff 0, NoNewPrivs 1 |
| Pod Security Admission rejects a privileged pod | PASS | server-side dry run |
| ArgoCD Application Synced and Healthy | NOT VERIFIED | ArgoCD or Application not present |
| Drift healed after kubectl scale | NOT VERIFIED | needs ArgoCD |
| Rollback by git revert | NOT VERIFIED | manual step, see docs/gitops.md |
