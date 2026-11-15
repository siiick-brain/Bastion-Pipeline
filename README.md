# Bastion Pipeline

A secure software delivery pipeline you can clone, run and break on purpose. The payload is small (a FastAPI notes service and a Windows package). The pipeline is the product: hash-locked builds, a hardened container, scanning gates, SBOMs, keyless signing, provenance verification, a release gate, GitOps deployment and signed updates.

The goal is evidence. Every claim below names a command, a date and a result. Status words follow [the glossary](docs/GLOSSARY.md): PASS, FAIL, NOT VERIFIED, PLANNED, NOT APPLICABLE.

## What it demonstrates

- Rejecting an untrusted artifact: a wrong signer, a wrong issuer, a tampered blob, a modified provenance claim and an unsigned image are each refused by a test you can run.
- Verifying origin, not just a signature: digest, certificate identity, issuer, workflow, ref, commit and runner.
- Verifying the running system, not configuration files: container and pod checks read `/proc` from the live process.
- One pipeline contract across GitHub Actions, GitLab CI and Jenkins, with the gaps stated.

## What it does not demonstrate

No cloud account, no production cluster, no real HSM and no real secure boot. SoftHSM and the firmware simulator are labelled as software. See [known limitations](docs/known-limitations.md).

## Pipeline

```mermaid
flowchart LR
  pr[Pull request] --> policy[Policy: author, title, style, workflow lint]
  pr --> test[Lint, types, tests, coverage 85]
  pr --> sec[Semgrep, Gitleaks, OSV, Trivy config, ZAP]
  test --> img[Image build, runtime tests, Trivy image gate]
  tag[Tag on main] --> rel[Build and push by digest]
  rel --> sign[Keyless sign, SBOMs, provenance]
  sign --> verify[Verify identity, provenance, SBOMs, tamper]
  verify --> gate[Release gate, production approval]
  gate --> pub[GitHub release]
  pub --> promote[promote.ps1 verifies, commits digest]
  promote --> argo[ArgoCD on kind]
```

Details: [architecture](docs/architecture.md), [threat model](docs/threat-model.md), [pipeline contract](docs/pipeline-contract.md), [control matrix](docs/control-matrix.md).

## Stages and tools

| Stage | Tools | Gate |
| --- | --- | --- |
| Source policy | commit-msg hook, `check-authorship.sh`, `check-style.ps1` | PR |
| Lint and types | ruff, mypy strict, yamllint, actionlint, zizmor, shellcheck, hadolint, PSScriptAnalyzer | PR |
| Tests | pytest with Hypothesis (coverage at least 85), Pester | PR, release |
| Container | multi-stage Chainguard image, runtime tests, Trivy | PR, release |
| SAST, secrets, SCA, IaC | Semgrep, Gitleaks, OSV-Scanner, dependency review, Trivy config, kubeconform | PR |
| DAST | ZAP baseline (PR), ZAP full (weekly) | PR |
| Supply chain | Syft (CycloneDX 1.6, SPDX 2.3), cosign keyless, GitHub provenance | Release |
| Release | `gate.py` in the `production` environment | Release |
| Deployment | kustomize, ArgoCD, `promote.ps1`, `verify-deployment.ps1` | Promotion |
| Updates | SoftHSM2 PKCS#11 signing, anti-rollback, firmware simulation | Container job |

Which tool owns which finding: [tool ownership](docs/tool-ownership.md).

## Results from real runs

Local runs on 2026-11-15 (Windows 11, Docker Desktop 29.9). Hosted runs have not happened since these changes, so they are NOT VERIFIED.

| Check | Command | Result |
| --- | --- | --- |
| Python tests and coverage | `pytest --cov` | PASS: 237 tests, 93.76 percent |
| Pester (Windows build and style) | `Invoke-Pester windows/tests tests/style` | PASS: 37 tests |
| Container runtime checks | `pytest tests/integration -m integration` | PASS: 11 tests |
| Real Sigstore identity checks | `pytest tests/integration -m network` | PASS: 7 tests |
| Image vulnerabilities, naive versus hardened | `trivy image` 0.76.2 | 15 critical and 491 high versus 0 and 0 ([hardening](docs/hardening.md)) |
| Image size, naive versus hardened | `docker image inspect` | 1.88 GB versus 122 MB |
| Signed update suite in SoftHSM container | `update-signing/run-demo.sh` | PASS: 55 tests, counter persists across runs |
| Jenkins pipeline, isolated agent | `infra/jenkins/run_job.py` | PASS: build 9 |
| Deployment on kind | `scripts/kind-demo.ps1` | PASS: 6 checks, 3 NOT VERIFIED ([report](docs/deployment-verification.md)) |
| Hosted GitHub workflows, release, OIDC demo, GitLab | | NOT VERIFIED |

## Quick start

```powershell
git clone https://github.com/siiick-brain/Bastion-Pipeline.git
cd Bastion-Pipeline
git config core.hooksPath scripts/hooks
python -m venv .venv
.venv/Scripts/python -m pip install --require-hashes --no-deps -r app/requirements-dev.txt
pwsh -File scripts/validate-pipeline.ps1
```

Prerequisites and every other command: [operations](docs/operations.md).

## Break it on purpose

| Try this | Expected |
| --- | --- |
| `pytest scripts/release/test_verify_provenance.py -v` | Ten tampered provenance cases rejected |
| `pytest tests/integration/test_supply_chain.py -m network -v` | Wrong workflow, ref, issuer and repository rejected by cosign against real Sigstore data |
| `pwsh -File scripts/kind-demo.ps1` | An unsigned image is refused before deployment |
| Two runs of the SoftHSM container | A downgrade is refused after a container restart |
| `pwsh -File scripts/make-gate-demos.ps1`, push a branch, open a PR | A secret, a vulnerable dependency, a failing test, an unpinned action or a root container turns a check red |

## Verify a release

[docs/verify.md](docs/verify.md) lists every command and a tamper that fails.

## Documentation

[Documentation index](docs/README.md) and [roadmap](docs/roadmap.md).
