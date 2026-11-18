<#
.SYNOPSIS
    Single local entry point: runs the same checks as the pull request gates.
.DESCRIPTION
    Each check reports PASS, FAIL or NOT VERIFIED (tool missing). The exit code is 1 when any
    check fails. Tools are looked up on PATH; the Python tools come from the locked .venv.
.EXAMPLE
    pwsh -File scripts/validate-pipeline.ps1
.EXAMPLE
    pwsh -File scripts/validate-pipeline.ps1 -SkipContainer
#>
[CmdletBinding()]
param(
    [switch]$SkipContainer,
    [string]$Python
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repoRoot
$results = [System.Collections.Generic.List[object]]::new()

if (-not $Python) {
    $venvPy = if ($IsWindows) { '.venv/Scripts/python.exe' } else { '.venv/bin/python' }
    $Python = if (Test-Path $venvPy) { $venvPy } else { 'python' }
}

function Invoke-Check {
    param([string]$Name, [string]$Tool, [scriptblock]$Body)
    if ($Tool -and -not (Get-Command $Tool -ErrorAction SilentlyContinue)) {
        $results.Add([pscustomobject]@{ Check = $Name; Status = 'NOT VERIFIED'; Detail = "$Tool not installed" })
        return
    }
    $global:LASTEXITCODE = 0
    try {
        & $Body *>&1 | Out-String | Set-Variable -Name output
        $status = if ($LASTEXITCODE -eq 0) { 'PASS' } else { 'FAIL' }
    } catch {
        $output = $_.ToString(); $status = 'FAIL'
    }
    $last = ($output.Trim() -split "`n" | Select-Object -Last 1)
    $results.Add([pscustomobject]@{ Check = $Name; Status = $status; Detail = $last })
}

try {
    Invoke-Check 'Style (docs/STYLE.md)' 'pwsh' { pwsh -NoProfile -File scripts/check-style.ps1 }
    Invoke-Check 'Ruff lint' '' { & $Python -m ruff check . --no-cache }
    Invoke-Check 'Ruff format' '' { & $Python -m ruff format --check . --no-cache }
    Invoke-Check 'Mypy strict' '' { & $Python -m mypy app scripts/oidc scripts/release update-signing/bastion_update firmware-sim/boot_sim.py }
    Invoke-Check 'Tests and coverage gate (85)' '' { & $Python -m pytest -p no:cacheprovider --cov --cov-fail-under=85 }
    Invoke-Check 'yamllint' '' { & $Python -m yamllint --strict . }
    Invoke-Check 'actionlint' 'actionlint' { actionlint }
    Invoke-Check 'zizmor' '' { & (Join-Path (Split-Path $Python) 'zizmor') --offline --min-severity low .github/workflows }
    Invoke-Check 'shellcheck' 'shellcheck' { shellcheck -x scripts/hooks/commit-msg scripts/check-authorship.sh scripts/verify-release.sh scripts/zap-scan.sh scripts/lib/commit-policy.sh }
    Invoke-Check 'hadolint' 'hadolint' { hadolint Dockerfile update-signing/Dockerfile infra/jenkins/Dockerfile.agent infra/jenkins/Dockerfile.controller }
    Invoke-Check 'Kustomize render' 'kubectl' { kubectl kustomize deploy/overlays/dev | Out-Null; kubectl kustomize deploy/overlays/prod | Out-Null }
    # Only history reachable from HEAD (skips local demo branches).
    Invoke-Check 'Gitleaks (history)' 'gitleaks' { gitleaks git . --log-opts=HEAD --redact --no-banner }
    Invoke-Check 'OSV-Scanner (lock files)' 'osv-scanner' { osv-scanner scan source --config osv-scanner.toml -L app/requirements.txt -L app/requirements-dev.txt -L update-signing/requirements.txt }
    Invoke-Check 'Trivy config' 'trivy' { trivy fs --scanners misconfig,secret --severity CRITICAL,HIGH --exit-code 1 --ignorefile .trivyignore.yaml --skip-dirs .venv,artifacts,zap-out,infra/jenkins/secrets --quiet . }
    if (-not $SkipContainer) {
        Invoke-Check 'Container build' 'docker' { docker build -q -t bastion-pipeline:local . }
        Invoke-Check 'Container runtime tests' 'docker' { & $Python -m pytest tests/integration -m integration -p no:cacheprovider }
        Invoke-Check 'Trivy image gate' 'trivy' { trivy image --scanners vuln --severity CRITICAL,HIGH --exit-code 1 --quiet bastion-pipeline:local }
    }
}
finally { Pop-Location }

$results | Format-Table -AutoSize -Wrap | Out-String -Width 200 | Write-Host
if ($results.Status -contains 'FAIL') { exit 1 }
exit 0
