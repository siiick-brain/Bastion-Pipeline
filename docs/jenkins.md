# Jenkins

## Design

| Element | Setting |
| --- | --- |
| Controller image | `jenkins/jenkins:lts-jdk21` 2.580.2, pinned by digest (`infra/jenkins/Dockerfile.controller`) |
| Plugins | Pinned in `infra/jenkins/plugins.txt` |
| Configuration | Configuration as Code (`infra/jenkins/casc.yaml`), setup wizard disabled |
| Controller executors | 0. Builds run only on the agent. |
| Agent | `jenkins/ssh-agent:latest-jdk21` pinned by digest, Python tool venv from the hash-locked `app/requirements-dev.txt`, Gitleaks and OSV-Scanner checked against publisher SHA-256 |
| Agent connection | SSH. Client key generated per setup. Agent host key pinned and verified with `known_hosts` (no trust on first use). |
| Secrets | `infra/jenkins/secrets/` (gitignored), mounted as Compose secrets. Masked by a tmpfs inside the agent's source mount. |
| Docker socket | Not mounted into any container. The agent has no Docker CLI. |
| Network exposure | UI on `127.0.0.1` only. The agent publishes no ports. |
| Job | `bastion-pipeline`, created by Job DSL from the read-only `Jenkinsfile`, runs in the Groovy sandbox |

## Trust boundaries

The controller holds credentials and configuration. The agent runs untrusted build steps. A compromised agent can affect its own workspace and the build result. It cannot reach the Docker daemon, read the controller's secrets (masked) or execute code on the controller (zero executors, sandboxed pipeline).

## Run it

```bash
JENKINS_PORT=8080 bash infra/jenkins/setup.sh
python infra/jenkins/run_job.py --url http://127.0.0.1:8080
```

## Evidence

| Check | Command | Date | Result |
| --- | --- | --- | --- |
| Pipeline runs all stages (source validation, lint, tests with coverage gate, secret scan, dependency analysis) | `run_job.py --url http://127.0.0.1:18081` | 2026-11-15 | PASS (build 9) |
| No container mounts `docker.sock` | `docker inspect bastion-jenkins-controller-1 bastion-jenkins-agent-1` | 2026-11-15 | PASS (0 matches) |
| Agent cannot read controller secrets | `docker exec bastion-jenkins-agent-1 cat /src/infra/jenkins/secrets/admin_password` | 2026-11-15 | PASS (file not present) |
| Agent host key verified after agent recreation | `docker compose up --force-recreate`, then build 9 | 2026-11-15 | PASS |
| The gates fail when they should | builds 2, 5 and 6 failed on a legacy commit title, an unformatted file and a fake secret before those were fixed | 2026-11-15 | PASS |

## Findings fixed during the audit

1. The agent's read-only source mount exposed the admin password and the controller's SSH key. Fixed with a tmpfs mask.
2. The first configuration trusted the agent host key on first use, so a replaced agent prompted for manual trust. Fixed with a pinned host key and `knownHostsFileKeyVerificationStrategy`.
3. The password file had a Windows line ending that became part of the password. `setup.sh` now writes no newline.

## Limits

- The agent is long-lived, not ephemeral per build.
- Job DSL script security is disabled for the seed script only (it reads `/src/Jenkinsfile`). The pipeline itself runs sandboxed.
- Container build, signing and release are NOT APPLICABLE on Jenkins by design (see [pipeline contract](pipeline-contract.md)).
