<#
.SYNOPSIS
    Verifies the running deployment, not the manifests, and writes docs/deployment-verification.md.
.DESCRIPTION
    Checks:
      1. The running pod's image digest equals the digest in the overlay.
      2. cosign verification passes for that digest.
      3. The process in the pod runs as a non-root UID with a read-only root filesystem,
         no capabilities and no privilege escalation (read from /proc inside the pod).
      4. Pod Security Admission rejects a privileged pod in the namespace.
      5. ArgoCD Application is Synced and Healthy (skipped when ArgoCD is absent).
      6. Drift is healed: a manual kubectl scale is reverted by ArgoCD (needs ArgoCD).
    Each check is PASS, FAIL or NOT VERIFIED. The exit code is 1 when any check FAILs.
.EXAMPLE
    pwsh -File scripts/verify-deployment.ps1 -Overlay dev -Tag v0.2.0
#>
[CmdletBinding()]
param(
    [string]$Overlay = 'dev',
    [string]$Namespace = 'bastion',
    [string]$Application = 'bastion-dev',
    [string]$Tag,
    [string]$PublicKey,
    [string]$Repository = 'siiick-brain/Bastion-Pipeline',
    [string]$Cosign = 'cosign',
    [switch]$AllowHttpRegistry,
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$Report = (Join-Path $PSScriptRoot '../docs/deployment-verification.md')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = $RepoRoot
$results = [System.Collections.Generic.List[object]]::new()

function Add-Result {
    param([string]$Check, [string]$Status, [string]$Evidence)
    $results.Add([pscustomobject]@{ Check = $Check; Status = $Status; Evidence = $Evidence })
    Write-Host ("{0,-13} {1}: {2}" -f $Status, $Check, $Evidence)
}

function Invoke-Kubectl {
    param([string[]]$Arguments)
    $out = & kubectl @Arguments 2>&1
    [pscustomobject]@{ Code = $LASTEXITCODE; Out = ($out -join "`n") }
}

$kz = Get-Content (Join-Path $repoRoot "deploy/overlays/$Overlay/kustomization.yaml") -Raw
$expectedDigest = if ($kz -match 'digest:\s*(sha256:[0-9a-f]{64})') { $Matches[1] } else { '' }
$imageName = if ($kz -match 'newName:\s*(\S+)') { $Matches[1] } else { '' }

# 1. Running digest
$pod = Invoke-Kubectl @('-n', $Namespace, 'get', 'pods', '-l', 'app.kubernetes.io/name=bastion-notes',
    '--field-selector=status.phase=Running', '-o', 'jsonpath={.items[0].metadata.name}')
$podName = $pod.Out.Trim()
if ($pod.Code -ne 0 -or -not $podName) {
    Add-Result 'Running digest equals signed digest' 'FAIL' 'no running pod'
} else {
    $imageId = (Invoke-Kubectl @('-n', $Namespace, 'get', 'pod', $podName, '-o', 'jsonpath={.status.containerStatuses[0].imageID}')).Out
    $status = if ($imageId.EndsWith("@$expectedDigest")) { 'PASS' } else { 'FAIL' }
    Add-Result 'Running digest equals signed digest' $status "pod $podName imageID ends $($imageId.Split('@')[-1].Substring(0, 19))..."
}

# 2. Signature
$ref = "$imageName@$expectedDigest"
if ($PublicKey) {
    $extra = @(); if ($AllowHttpRegistry) { $extra += '--allow-http-registry' }
    & $Cosign verify --key $PublicKey --insecure-ignore-tlog=true @extra $ref *> $null
} elseif ($Tag) {
    & $Cosign verify $ref --certificate-identity "https://github.com/$Repository/.github/workflows/release.yml@refs/tags/$Tag" `
        --certificate-oidc-issuer https://token.actions.githubusercontent.com *> $null
} else { $global:LASTEXITCODE = -1 }
if ($LASTEXITCODE -eq -1) { Add-Result 'cosign verify passes' 'NOT VERIFIED' 'pass -Tag or -PublicKey' }
else { Add-Result 'cosign verify passes' ($(if ($LASTEXITCODE -eq 0) { 'PASS' } else { 'FAIL' })) $ref }

# 3. Effective security context, read from the running process
if ($podName) {
    $probe = "import os;s=open('/proc/1/status').read();u=[l for l in s.splitlines() if l.startswith(('Uid','CapEff','NoNewPrivs'))];print(';'.join(u))`ntry:`n open('/srv/app/x','w')`n print('WRITABLE')`nexcept OSError as e:`n print('RO' if e.errno==30 else 'ERR'+str(e.errno))"
    $p = Invoke-Kubectl @('-n', $Namespace, 'exec', $podName, '-c', 'app', '--', '/usr/bin/python', '-c', $probe)
    $uidOk = $p.Out -match 'Uid:\s+65532\s+65532\s+65532\s+65532'
    $capOk = $p.Out -match 'CapEff:\s+0000000000000000'
    $nnpOk = $p.Out -match 'NoNewPrivs:\s+1'
    $roOk = $p.Out -match '\bRO\b'
    Add-Result 'Process runs as UID 65532 (non-root)' ($(if ($uidOk) { 'PASS' } else { 'FAIL' })) 'from /proc/1/status in the pod'
    Add-Result 'Root filesystem is read-only' ($(if ($roOk) { 'PASS' } else { 'FAIL' })) 'write to /srv/app returned EROFS'
    Add-Result 'No capabilities, no privilege escalation' ($(if ($capOk -and $nnpOk) { 'PASS' } else { 'FAIL' })) 'CapEff 0, NoNewPrivs 1'
} else {
    foreach ($c in 'Process runs as UID 65532 (non-root)', 'Root filesystem is read-only', 'No capabilities, no privilege escalation') {
        Add-Result $c 'NOT VERIFIED' 'no running pod'
    }
}

# 4. Admission rejects a privileged pod
$bad = @"
apiVersion: v1
kind: Pod
metadata: {name: psa-probe, namespace: $Namespace}
spec:
  containers: [{name: c, image: $ref, securityContext: {privileged: true}}]
"@
$r = $bad | & kubectl apply --dry-run=server -f - 2>&1
$rejected = ($LASTEXITCODE -ne 0) -and (($r -join ' ') -match 'violates PodSecurity')
Add-Result 'Pod Security Admission rejects a privileged pod' ($(if ($rejected) { 'PASS' } else { 'FAIL' })) 'server-side dry run'

# 5 and 6. ArgoCD
$app = Invoke-Kubectl @('-n', 'argocd', 'get', 'application', $Application, '-o', 'jsonpath={.status.sync.status}/{.status.health.status}')
if ($app.Code -ne 0) {
    Add-Result 'ArgoCD Application Synced and Healthy' 'NOT VERIFIED' 'ArgoCD or Application not present'
    Add-Result 'Drift healed after kubectl scale' 'NOT VERIFIED' 'needs ArgoCD'
} else {
    Add-Result 'ArgoCD Application Synced and Healthy' ($(if ($app.Out -eq 'Synced/Healthy') { 'PASS' } else { 'FAIL' })) $app.Out
    $want = (Invoke-Kubectl @('-n', $Namespace, 'get', 'deploy', 'bastion-notes', '-o', 'jsonpath={.spec.replicas}')).Out
    Invoke-Kubectl @('-n', $Namespace, 'scale', 'deploy/bastion-notes', '--replicas=3') | Out-Null
    $healed = $false
    for ($i = 0; $i -lt 36 -and -not $healed; $i++) {
        Start-Sleep -Seconds 5
        $healed = (Invoke-Kubectl @('-n', $Namespace, 'get', 'deploy', 'bastion-notes', '-o', 'jsonpath={.spec.replicas}')).Out -eq $want
    }
    Add-Result 'Drift healed after kubectl scale' ($(if ($healed) { 'PASS' } else { 'FAIL' })) "scaled to 3, restored to $want"
}
Add-Result 'Rollback by git revert' 'NOT VERIFIED' 'manual step, see docs/gitops.md'

$date = (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd')
$lines = @('# Deployment verification', '', "Date: $date. Command: ``pwsh -File scripts/verify-deployment.ps1 -Overlay $Overlay``.", '',
    "Overlay: ``$Overlay``. Image: ``$ref``.", '', '| Check | Status | Evidence |', '| --- | --- | --- |')
foreach ($res in $results) { $lines += "| $($res.Check) | $($res.Status) | $($res.Evidence.Replace('|', '/')) |" }
[System.IO.File]::WriteAllText([System.IO.Path]::GetFullPath($Report), ($lines -join "`n") + "`n")
Write-Host "Report written: $Report"

if ($results.Status -contains 'FAIL') { exit 1 }
exit 0
