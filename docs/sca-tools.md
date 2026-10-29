# SCA tool gate plan

This short guide records which tools gate pull requests and which tools run deeper scans.

## Pull request gates

- Semgrep
- Gitleaks
- Trivy filesystem and config checks
- OSV-Scanner
- Dependency review

## Deep scan jobs

- Dependency-Check weekly job
- ZAP full scans on the demo app
- Container image scanning on the release path
- SonarCloud quality gate with explicit wait
