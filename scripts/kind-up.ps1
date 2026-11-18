<#
.SYNOPSIS
    Creates the local kind cluster, a local registry on 127.0.0.1:5001 and (optionally) ArgoCD
    and the Kyverno admission policy.
.DESCRIPTION
    Idempotent. Uses only pinned images and SHA-256 checked manifests (infra/argocd/versions.env,
    infra/kyverno/versions.env). Nothing is exposed beyond 127.0.0.1.
    -WithAdmission installs Kyverno and infra/kyverno/require-signed-images.yaml: pods in the
    bastion namespace must run the project image by digest, signed by the release workflow.
.EXAMPLE
    pwsh -File scripts/kind-up.ps1 -WithArgoCD -WithAdmission
#>
[CmdletBinding()]
param(
    [switch]$WithArgoCD,
    [switch]$WithAdmission,
    [string]$ClusterName = 'bastion'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Invoke-Native {
    param([Parameter(Mandatory)][string]$File, [string[]]$Arguments)
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$File $($Arguments -join ' ') failed with exit code $LASTEXITCODE" }
}

$versions = @{}
foreach ($file in 'infra/argocd/versions.env', 'infra/kyverno/versions.env') {
    foreach ($line in Get-Content (Join-Path $repoRoot $file)) {
        if ($line -match '^\s*([A-Z0-9_]+)=(.+)$') { $versions[$Matches[1]] = $Matches[2].Trim() }
    }
}

function Install-PinnedManifest {
    param([string]$Name, [string]$Url, [string]$Sha256, [string]$Namespace)
    $manifest = Join-Path ([System.IO.Path]::GetTempPath()) "$Name-install.yaml"
    Invoke-WebRequest -Uri $Url -OutFile $manifest -UseBasicParsing
    $hash = (Get-FileHash -Algorithm SHA256 $manifest).Hash.ToLowerInvariant()
    if ($hash -ne $Sha256) {
        Remove-Item $manifest -Force
        throw "$Name manifest hash mismatch: expected $Sha256, got $hash"
    }
    & kubectl create namespace $Namespace --dry-run=client -o yaml | & kubectl apply -f -
    Invoke-Native kubectl @('apply', '--server-side', '--force-conflicts', '-n', $Namespace, '-f', $manifest)
    Remove-Item $manifest -Force
}

foreach ($tool in 'docker', 'kind', 'kubectl') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Missing prerequisite: $tool" }
}

$existing = @(& kind get clusters 2>$null)
if ($existing -notcontains $ClusterName) {
    Invoke-Native kind @('create', 'cluster', '--config', (Join-Path $repoRoot 'infra/kind/cluster.yaml'), '--wait', '120s')
} else {
    Write-Host "Cluster $ClusterName already exists."
}

$reg = 'kind-registry'
$running = (& docker inspect -f '{{.State.Running}}' $reg 2>$null)
if ($running -ne 'true') {
    & docker rm -f $reg *> $null
    Invoke-Native docker @('run', '-d', '--restart=unless-stopped', '--name', $reg, '-p', '127.0.0.1:5001:5000', $versions.REGISTRY_IMAGE)
}
& docker network connect kind $reg 2>$null

$hosts = "[host.`"http://${reg}:5000`"]`n"
foreach ($node in & kind get nodes --name $ClusterName) {
    Invoke-Native docker @('exec', $node, 'mkdir', '-p', '/etc/containerd/certs.d/localhost:5001')
    $hosts | & docker exec -i $node sh -c 'cat > /etc/containerd/certs.d/localhost:5001/hosts.toml'
    if ($LASTEXITCODE -ne 0) { throw "failed to configure registry mirror on $node" }
}

if ($WithArgoCD) {
    Install-PinnedManifest -Name 'argocd' -Url $versions.ARGOCD_INSTALL_URL -Sha256 $versions.ARGOCD_INSTALL_SHA256 -Namespace 'argocd'
    Invoke-Native kubectl @('-n', 'argocd', 'rollout', 'status', 'deploy/argocd-repo-server', '--timeout=300s')
    Invoke-Native kubectl @('-n', 'argocd', 'rollout', 'status', 'statefulset/argocd-application-controller', '--timeout=300s')
    Write-Host "ArgoCD $($versions.ARGOCD_VERSION) installed (manifest SHA-256 verified)."
}

if ($WithAdmission) {
    Install-PinnedManifest -Name 'kyverno' -Url $versions.KYVERNO_INSTALL_URL -Sha256 $versions.KYVERNO_INSTALL_SHA256 -Namespace 'kyverno'
    Invoke-Native kubectl @('-n', 'kyverno', 'rollout', 'status', 'deploy/kyverno-admission-controller', '--timeout=300s')
    # The Kyverno policy webhook can lag the rollout.
    $policy = Join-Path $repoRoot 'infra/kyverno/require-signed-images.yaml'
    foreach ($attempt in 1..10) {
        & kubectl apply -f $policy
        if ($LASTEXITCODE -eq 0) { break }
        if ($attempt -eq 10) { throw "Could not apply $policy" }
        Start-Sleep -Seconds 6
    }
    foreach ($resource in 'validatingpolicy.policies.kyverno.io/bastion-project-image-by-digest', 'imagevalidatingpolicy.policies.kyverno.io/bastion-release-signature') {
        Invoke-Native kubectl @('wait', '--for=jsonpath={.status.conditionStatus.ready}=true', $resource, '--timeout=120s')
    }
    Write-Host "Kyverno $($versions.KYVERNO_VERSION) installed (manifest SHA-256 verified); signature policy enforced in namespace bastion."
}

Write-Host "Cluster $ClusterName ready. Registry: localhost:5001 (bound to 127.0.0.1)."
