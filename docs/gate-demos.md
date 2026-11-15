# Gate demonstrations

`scripts/make-gate-demos.ps1` creates five local throwaway branches. Each holds one commit with one deliberate violation. Push one and open a pull request to watch the matching check turn red. Never merge them.

| Branch | Violation | Blocking check | Local confirmation (2026-11-15) | Hosted PR |
| --- | --- | --- | --- | --- |
| `gate-demo/fake-secret` | Random fake API key labelled as fake in `app/demo_settings.py` | Secrets (Gitleaks) | NOT VERIFIED | NOT VERIFIED |
| `gate-demo/vuln-dependency` | `jinja2==2.10` in `app/requirements.txt` | SCA gate (OSV-Scanner) | PASS: OSV-Scanner reports 6 vulnerabilities (2 high, 4 medium) | NOT VERIFIED |
| `gate-demo/failing-test` | Test expects HTTP 500 from `/health` | build-test (pytest) | NOT VERIFIED | NOT VERIFIED |
| `gate-demo/unpinned-action` | `aquasecurity/trivy-action@master` | policy (zizmor) | NOT VERIFIED | NOT VERIFIED |
| `gate-demo/root-container` | `USER root` in `Dockerfile` | container (runtime test) and IaC (Trivy config) | NOT VERIFIED | NOT VERIFIED |

The script requires a clean working tree, uses the configured Git identity (so the commit-msg hook applies) and returns to the starting branch. `-WhatIf` lists the branches without creating them.

The fake key is generated at run time, so the main branch contains no secret pattern. Gitleaks ignores the AWS documentation example keys, which is why a random value is used. `scripts/verify-skills.ps1` proves Gitleaks detects this form (row 9).
