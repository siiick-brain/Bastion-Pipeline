param(
    [string]$Image = 'ghcr.io/example/bastion-pipeline:latest',
    [string]$TargetManifest = 'deploy/dev/kustomization.yaml',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command cosign -ErrorAction SilentlyContinue)) {
    throw 'cosign is required to verify the signed image.'
}

if ($DryRun) {
    Write-Host "Dry run: cosign verify $Image"
    Write-Host "Dry run: update $TargetManifest with the verified digest"
    return
}

cosign verify $Image
Write-Host "Image verified: $Image"
Write-Host "Update the digest in $TargetManifest after the verified promotion step."
