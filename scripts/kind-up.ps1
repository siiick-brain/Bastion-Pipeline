<#
.SYNOPSIS
    Creates the local kind cluster, a local registry on 127.0.0.1:5001 and (optionally) ArgoCD.
.DESCRIPTION
    Idempotent. Uses only pinned images and a SHA-256 checked ArgoCD manifest
    (infra/argocd/versions.env). Nothing is exposed beyond 127.0.0.1.
.EXAMPLE
    pwsh -File scripts/kind-up.ps1 -WithArgoCD
#>
[CmdletBinding()]
param(
    [switch]$WithArgoCD,
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
foreach ($line in Get-Content (Join-Path $repoRoot 'infra/argocd/versions.env')) {
    if ($line -match '^\s*([A-Z0-9_]+)=(.+)$') { $versions[$Matches[1]] = $Matches[2].Trim() }
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
    $manifest = Join-Path ([System.IO.Path]::GetTempPath()) "argocd-install-$($versions.ARGOCD_VERSION).yaml"
    Invoke-WebRequest -Uri $versions.ARGOCD_INSTALL_URL -OutFile $manifest -UseBasicParsing
    $hash = (Get-FileHash -Algorithm SHA256 $manifest).Hash.ToLowerInvariant()
    if ($hash -ne $versions.ARGOCD_INSTALL_SHA256) {
        Remove-Item $manifest -Force
        throw "ArgoCD manifest hash mismatch: expected $($versions.ARGOCD_INSTALL_SHA256), got $hash"
    }
    & kubectl create namespace argocd --dry-run=client -o yaml | & kubectl apply -f -
    Invoke-Native kubectl @('apply', '--server-side', '--force-conflicts', '-n', 'argocd', '-f', $manifest)
    Invoke-Native kubectl @('-n', 'argocd', 'rollout', 'status', 'deploy/argocd-repo-server', '--timeout=300s')
    Invoke-Native kubectl @('-n', 'argocd', 'rollout', 'status', 'statefulset/argocd-application-controller', '--timeout=300s')
    Remove-Item $manifest -Force
    Write-Host "ArgoCD $($versions.ARGOCD_VERSION) installed (manifest SHA-256 verified)."
}

Write-Host "Cluster $ClusterName ready. Registry: localhost:5001 (bound to 127.0.0.1)."
