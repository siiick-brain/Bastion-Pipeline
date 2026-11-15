# ADR 0002: Scanner split

Date: 2026-11-15. Status: Accepted.

## Context

The specification lists Semgrep, SonarCloud, Gitleaks, Trivy, OSV-Scanner, dependency review, Dependency-Check and ZAP. Running several scanners on the same target produces duplicate findings and slows pull requests.

## Decision

Each finding class has one blocking owner on pull requests. Overlapping tools run on a schedule as a second opinion. The full table is in [tool ownership](../tool-ownership.md).

| Finding class | PR gate (blocks) | Scheduled or advisory |
| --- | --- | --- |
| Python dependencies | OSV-Scanner on lock files | Dependency-Check weekly, OSV full scan weekly |
| New dependencies in a PR | dependency-review-action | |
| Code (SAST) | Semgrep, ERROR severity | SonarCloud quality gate (when configured) |
| Secrets | Gitleaks, full history | |
| Image OS and language packages | Trivy image | OSV image scan weekly |
| IaC and Dockerfile | Trivy config, hadolint, kubeconform | |
| Running app | ZAP baseline | ZAP full scan weekly |

## Consequences

- `safety` was removed from GitLab CI and Jenkins: it now needs an account key and duplicates OSV-Scanner.
- `|| true` was removed from every security step. A scanner that cannot fail is not a gate.
