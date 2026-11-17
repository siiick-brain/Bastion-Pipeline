# Deployment verification

Date: 2026-11-17. Command: `pwsh -File scripts/verify-deployment.ps1 -Overlay dev`.

Overlay: `dev`. Image: `ghcr.io/siiick-brain/bastion-pipeline@sha256:706f6b48b24903b5b8e97bcc70e3619a682acd41ab0fb9667a2be9ac52ec3c00`.

| Check | Status | Evidence |
| --- | --- | --- |
| Running digest equals signed digest | PASS | pod bastion-notes-65cc965b6-rt7g5 imageID ends sha256:706f6b48b249... |
| cosign verify passes | PASS | ghcr.io/siiick-brain/bastion-pipeline@sha256:706f6b48b24903b5b8e97bcc70e3619a682acd41ab0fb9667a2be9ac52ec3c00 |
| Process runs as UID 65532 (non-root) | PASS | from /proc/1/status in the pod |
| Root filesystem is read-only | PASS | write to /srv/app returned EROFS |
| No capabilities, no privilege escalation | PASS | CapEff 0, NoNewPrivs 1 |
| Pod Security Admission rejects a privileged pod | PASS | server-side dry run |
| ArgoCD Application Synced and Healthy | PASS | Synced/Healthy |
| Drift healed after kubectl scale | PASS | scaled to 3, restored to 1 |
| Rollback by git revert | NOT VERIFIED | manual step, see docs/gitops.md |
