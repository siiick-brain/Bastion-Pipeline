# DAST

## Scope

- Targets are only containers started by this project on a local Docker network: the notes service (`app`) and OWASP Juice Shop (`juice`) for the demonstration.
- `scripts/zap-scan.sh` refuses any other target (exit code 2). A run against `http://example.com:80` was refused on 2026-11-15.
- Juice Shop runs on an `--internal` Docker network with no published ports. It is never deployed anywhere.
- ZAP image: `ghcr.io/zaproxy/zaproxy:stable` pinned by digest (ZAP 2.17.0 on 2026-11-15).

## Notes service baseline (pull request gate)

Command: `docker compose up -d --wait` then `bash scripts/zap-scan.sh baseline http://app:8000 zap-baseline`. Date: 2026-11-15.

| Run | Result | Detail |
| --- | --- | --- |
| Before the header fix | WARN | 67 pass, 1 warning: 10049 Storable and Cacheable Content |
| After `Cache-Control: no-store` and security headers | PASS (exit 0) | 67 pass, 0 warnings, 0 failures, 1 ignored: 10049 Non-Storable Content (EX-003, the intended result) |

The app scan runs without `-I`, so any new warning fails the job.

## Juice Shop demonstration (manual workflow)

Workflow: `.github/workflows/dast-demo.yml` (`workflow_dispatch` only). The same scan was run locally on 2026-11-15 with `DAST_NETWORK=dast-demo bash scripts/zap-scan.sh baseline http://juice:3000 juice-shop`. The demo uses `-I` so findings are reported without failing.

| Risk | Alert types | Alerts |
| --- | --- | --- |
| High | 1 | 10003 Vulnerable JS Library |
| Medium | 2 | 10038 Content Security Policy header not set, 10098 Cross-Domain Misconfiguration |
| Low | 2 | 10017 Cross-Domain JavaScript Source File Inclusion, 10096 Timestamp Disclosure |
| Informational | 1 | 10109 Modern Web Application |

56 rules passed. A baseline scan is passive, so it finds header and library issues, not the injection flaws Juice Shop also contains. Hosted workflow run: NOT VERIFIED.
