# Operations

## Prerequisites

| Tool | Tested version | Needed for |
| --- | --- | --- |
| Python | 3.11 or later (3.14 tested locally, 3.12 in CI) | tests, verifiers |
| PowerShell | 7.7 | scripts, Pester 6.2.0, PSScriptAnalyzer 1.25.0 |
| Docker Desktop | 29.9 | images, Jenkins, SoftHSM, ZAP |
| kind, kubectl | 0.33.0, 1.36.1 | local cluster |
| cosign, syft, trivy | 3.1.4, 1.55.0, 0.76.2 | supply chain |
| gitleaks, osv-scanner, hadolint, actionlint, shellcheck | 8.30.1, 2.2.4, 2.14.0, 1.7.12, any | local gates |
| gh | any recent | releases, rulesets |

On Windows these install with winget: `Microsoft.PowerShell`, `Kubernetes.kind`, `AquaSecurity.Trivy`, `Anchore.Syft`, `Sigstore.Cosign`, `hadolint.hadolint`, `rhysd.actionlint`, `koalaman.shellcheck`, `Kubernetes.kustomize`, `Google.OSVScanner`, `jqlang.jq`.

## First setup

```powershell
git clone https://github.com/siiick-brain/Bastion-Pipeline.git
cd Bastion-Pipeline
git config core.hooksPath scripts/hooks
python -m venv .venv
.venv/Scripts/python -m pip install --require-hashes --no-deps -r app/requirements-dev.txt
Install-Module Pester -RequiredVersion 6.2.0 -Scope CurrentUser
Install-Module PSScriptAnalyzer -RequiredVersion 1.25.0 -Scope CurrentUser
pwsh -File scripts/validate-pipeline.ps1
```

## Routine tasks

| Task | Command |
| --- | --- |
| All local gates | `pwsh -File scripts/validate-pipeline.ps1` |
| Windows package | `windows\build.bat -Version 0.2.0 -BuildNumber 1` |
| Local cluster with ArgoCD | `pwsh -File scripts/kind-up.ps1 -WithArgoCD` |
| Local deployment demo | `pwsh -File scripts/kind-demo.ps1` |
| Jenkins | `bash infra/jenkins/setup.sh` then `python infra/jenkins/run_job.py --url http://127.0.0.1:8080` |
| Signed update demo | see [PKCS#11 and SoftHSM](pkcs11-softhsm.md) |
| Release | `git tag -s v0.2.0 && git push origin v0.2.0`, then approve the `production` gate |
| Promote a release | `pwsh -File scripts/promote.ps1 -Image <image@digest> -Tag <tag>` |
| Branch ruleset | `pwsh -File scripts/apply-branch-protection.ps1` (dry run), then `-Apply` |
| Gate demonstrations | `pwsh -File scripts/make-gate-demos.ps1` |

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `No module named uvicorn` in the container | Build and runtime Python differ | Use the provided `Dockerfile`; `test_container.py` catches this |
| `requires the httpx2 package` | Old lock file | Reinstall from `app/requirements-dev.txt` |
| Volume mounts empty on Windows | Git Bash path rewriting | `export MSYS_NO_PATHCONV=1` or use PowerShell |
| Jenkins `401 Unauthorized` | Password file with a trailing newline | Delete `infra/jenkins/secrets/admin_password` and rerun `setup.sh` |
| Jenkins agent offline after recreation | Host key mismatch | Rerun `setup.sh` so `known_hosts` matches `agent_host_key` |
| `promote.ps1` refuses an image | Tag instead of digest, verification failed | Pass `name@sha256:...` and the correct `-Tag` |
| Release gate blocked with NOT VERIFIED | Evidence missing from an earlier job | Read `gate-summary.md`; fix the failing job; do not edit the gate |
| Docker Desktop stops | Memory pressure | Stop unused containers, then restart Docker Desktop |

## Cleanup

```powershell
kind delete cluster --name bastion
docker rm -f kind-registry
docker compose -f infra/jenkins/compose.yaml down -v
docker compose down -v
docker volume rm bastion-update-state
```
