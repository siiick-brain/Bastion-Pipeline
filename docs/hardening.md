# Container hardening

## Before and after

Command: `trivy image --scanners vuln --format json <image>` with Trivy 0.76.2 on 2026-11-15. Both images contain the same app. Evidence: `artifacts/scans/trivy-naive.json` and `artifacts/scans/trivy-local.json` (regenerate with the commands below).

| Image | Dockerfile | Base | Size | Critical | High | Medium | Low | Unknown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Naive | `Dockerfile.naive` | `python:3.11` single stage, root, dev tools | 1.88 GB | 15 | 491 | 805 | 1306 | 82 |
| Hardened | `Dockerfile` | Chainguard Python, multi-stage, digest pinned | 122 MB | 0 | 0 | 0 | 0 | 0 |

Reproduce:

```powershell
docker build -t bastion-pipeline:local .
docker build -f Dockerfile.naive -t bastion-pipeline:naive .
trivy image --scanners vuln bastion-pipeline:naive
trivy image --scanners vuln --severity CRITICAL,HIGH --exit-code 1 bastion-pipeline:local
```

An intermediate measurement on the same day explains the base image choice ([ADR 0004](adr/0004-container-base-image.md)): distroless Debian 12 had 2 critical and 123 high findings, distroless Debian 13 had 0 critical and 89 high.

## Image properties and how they are verified

Static claims are not enough. `tests/integration/test_container.py` starts the image with the pod's restrictions and checks the running process (11 tests, PASS on 2026-11-15, `pytest tests/integration -m integration`).

| Property | Dockerfile | Runtime test |
| --- | --- | --- |
| Base images pinned by digest | both `FROM` lines | hadolint, Dependabot |
| Multi-stage, runtime deps only | `--target /home/nonroot/deps -r requirements.txt` | `test_no_dev_tools_in_image` |
| Non-root UID 65532 | `USER 65532:65532` | `test_process_runs_as_nonroot_uid` reads `/proc/1/status` |
| No shell | Chainguard runtime image | `test_no_shell_in_image` (`/bin/sh`, `/bin/bash`, `/busybox/sh`) |
| Code not writable by the app | files owned by root | `test_application_code_not_owned_by_runtime_user` |
| Works with a read-only root filesystem | no writes at runtime | `test_root_filesystem_is_not_writable`, `test_health_responds_under_read_only_root` |
| No capabilities, no privilege escalation | (runtime flags) | `test_effective_capabilities_are_empty` reads `CapEff`, `CapBnd`, `NoNewPrivs` |
| No embedded credentials | no `ENV` secrets | `test_image_config_is_hardened`, Trivy secret scanner |
| No `Server` header | `--no-server-header` | `test_health_responds_under_read_only_root` |

## Kubernetes security context

`deploy/base/deployment.yaml`: `runAsNonRoot`, UID and GID 65532, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, `privileged: false`, all capabilities dropped, seccomp `RuntimeDefault`, CPU, memory and ephemeral storage requests and limits, readiness and liveness probes, no service account token. The namespace enforces Pod Security `restricted`. A default-deny NetworkPolicy allows only in-namespace traffic to port 8000. The Service is `ClusterIP`.

Runtime verification on kind: see [deployment verification](deployment-verification.md).

## Health check

The image has no `HEALTHCHECK` instruction because it has no shell or curl. Kubernetes probes and the Compose healthcheck call `/health` (exception EX-002 in `security/exceptions.toml`).
