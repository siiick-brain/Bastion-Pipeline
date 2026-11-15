<#
.SYNOPSIS
    Local end-to-end deployment demonstration on kind, without a registry account.
.DESCRIPTION
    1. Builds the hardened image and pushes it to the local registry (localhost:5001).
    2. Signs the pushed digest with a local cosign key (artifacts/kind/cosign.key).
    3. Copies deploy/ into artifacts/kind/repo and promotes the digest into overlay "local"
       with scripts/promote.ps1, which refuses to promote unless cosign verification passes.
    4. Applies the overlay, waits for rollout, then runs scripts/verify-deployment.ps1.
    Also demonstrates that promote.ps1 refuses an unsigned digest.
    The GitHub release path uses keyless signing instead; see docs/gitops.md.
.EXAMPLE
    pwsh -File scripts/kind-demo.ps1
#>
[CmdletBinding()]
param(
    [string]$Cosign = 'cosign',
    [string]$Report = (Join-Path $PSScriptRoot '../docs/deployment-verification.md')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$work = Join-Path $repoRoot 'artifacts/kind'
$demoRepo = Join-Path $work 'repo'

function Invoke-Native {
    param([Parameter(Mandatory)][string]$File, [string[]]$Arguments)
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$File $($Arguments -join ' ') failed with exit code $LASTEXITCODE" }
}

New-Item -ItemType Directory -Force -Path $work | Out-Null
$image = 'localhost:5001/bastion-pipeline'
Invoke-Native docker @('build', '-q', '-t', "${image}:demo", $repoRoot)
Invoke-Native docker @('push', '-q', "${image}:demo")
$digest = (& docker buildx imagetools inspect "${image}:demo" --format '{{json .Manifest.Digest}}').Trim('"')
if ($digest -notmatch '^sha256:[0-9a-f]{64}$') { throw "could not resolve pushed digest: $digest" }
$ref = "$image@$digest"
Write-Host "Pushed $ref"

# Unsigned image must not be promotable: push a second, unsigned image and try.
Invoke-Native docker @('build', '-q', '--label', 'bastion.demo=unsigned', '-t', "${image}:unsigned", $repoRoot)
Invoke-Native docker @('push', '-q', "${image}:unsigned")
$unsigned = (& docker buildx imagetools inspect "${image}:unsigned" --format '{{json .Manifest.Digest}}').Trim('"')

$env:COSIGN_PASSWORD = ''
$env:COSIGN_YES = 'true'
$key = Join-Path $work 'cosign.key'
if (-not (Test-Path $key)) {
    Push-Location $work
    try { Invoke-Native $Cosign @('generate-key-pair') } finally { Pop-Location }
}
$pub = Join-Path $work 'cosign.pub'
Invoke-Native $Cosign @('sign', '--key', $key, '--tlog-upload=false', '--use-signing-config=false', '--allow-http-registry', $ref)

if (Test-Path $demoRepo) { Remove-Item -Recurse -Force -LiteralPath $demoRepo }
New-Item -ItemType Directory -Force -Path (Join-Path $demoRepo 'deploy/overlays/local') | Out-Null
Copy-Item -Recurse (Join-Path $repoRoot 'deploy/base') (Join-Path $demoRepo 'deploy/base')
@"
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
images:
  - name: bastion-notes
    newName: $image
    digest: sha256:0000000000000000000000000000000000000000000000000000000000000000
"@ | Set-Content -Encoding utf8 (Join-Path $demoRepo 'deploy/overlays/local/kustomization.yaml')

$promote = Join-Path $PSScriptRoot 'promote.ps1'
if (Get-Variable unsigned -ErrorAction SilentlyContinue) {
    & (Get-Process -Id $PID).Path -NoProfile -File $promote -Image "$image@$unsigned" -Overlay local -PublicKey $pub `
        -AllowHttpRegistry -RepoRoot $demoRepo -Cosign $Cosign *> $null
    if ($LASTEXITCODE -eq 0) { throw 'promote.ps1 accepted an unsigned image' }
    Write-Host 'promote.ps1 refused the unsigned image (expected).'
}
& (Get-Process -Id $PID).Path -NoProfile -File $promote -Image $ref -Overlay local -PublicKey $pub `
    -AllowHttpRegistry -RepoRoot $demoRepo -Cosign $Cosign
if ($LASTEXITCODE -ne 0) { throw 'promotion failed' }

Invoke-Native kubectl @('apply', '-k', (Join-Path $demoRepo 'deploy/overlays/local'))
Invoke-Native kubectl @('-n', 'bastion', 'rollout', 'status', 'deploy/bastion-notes', '--timeout=180s')

& (Get-Process -Id $PID).Path -NoProfile -File (Join-Path $PSScriptRoot 'verify-deployment.ps1') -Overlay local `
    -RepoRoot $demoRepo -PublicKey $pub -AllowHttpRegistry -Cosign $Cosign -Report $Report
exit $LASTEXITCODE
