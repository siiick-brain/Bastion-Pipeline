<#
.SYNOPSIS
    Verifies an image signature with cosign, then writes the verified digest into an overlay.
.DESCRIPTION
    Refuses tags: the image must be given as name@sha256:<digest>. Verification is keyless by
    default (exact certificate identity and issuer of the release workflow). -PublicKey is for
    the local kind demonstration where images are signed with a local key.
    The script edits deploy/overlays/<Overlay>/kustomization.yaml and prints the diff. It never
    commits: the owner reviews and commits the change, and ArgoCD deploys it.
.EXAMPLE
    pwsh -File scripts/promote.ps1 -Image ghcr.io/siiick-brain/bastion-pipeline@sha256:... -Tag v0.2.0
.EXAMPLE
    pwsh -File scripts/promote.ps1 -Image localhost:5001/bastion-pipeline@sha256:... -PublicKey artifacts/kind/cosign.pub -Overlay local
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$Image,
    [string]$Overlay = 'dev',
    [string]$Tag,
    [string]$Repository = 'siiick-brain/Bastion-Pipeline',
    [string]$PublicKey,
    # winget installs cosign under its release asset name.
    [string]$Cosign = $(if (Get-Command cosign -ErrorAction SilentlyContinue) { 'cosign' } else { 'cosign-windows-amd64' }),
    [switch]$AllowHttpRegistry,
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Image -notmatch '^(?<name>[a-z0-9][a-z0-9._/:-]*[a-z0-9])@(?<digest>sha256:[0-9a-f]{64})$') {
    throw "Image must be name@sha256:<64 hex>. Tags are not promoted. Got: $Image"
}
$name = $Matches.name
$digest = $Matches.digest
if ($Overlay -notmatch '^[a-z0-9-]+$') { throw "Invalid overlay name: $Overlay" }
$kustomization = Join-Path $RepoRoot "deploy/overlays/$Overlay/kustomization.yaml"
if (-not (Test-Path -LiteralPath $kustomization)) { throw "Overlay not found: $kustomization" }

if ($PublicKey) {
    $verifyArgs = @('verify', '--key', $PublicKey, '--insecure-ignore-tlog=true', $Image)
    if ($AllowHttpRegistry) { $verifyArgs += '--allow-http-registry' }
} else {
    if ($Tag -notmatch '^v\d+\.\d+\.\d+$') { throw 'Keyless verification needs -Tag vX.Y.Z (the release tag that signed the image).' }
    $identity = "https://github.com/$Repository/.github/workflows/release.yml@refs/tags/$Tag"
    $verifyArgs = @('verify', $Image, '--certificate-identity', $identity,
        '--certificate-oidc-issuer', 'https://token.actions.githubusercontent.com')
}

Write-Host "Verifying signature: $Image"
& $Cosign @verifyArgs *> $null
if ($LASTEXITCODE -ne 0) { throw "cosign verification FAILED for $Image. Nothing was promoted." }
Write-Host 'Signature verified.'

$text = [System.IO.File]::ReadAllText($kustomization)
# [ \t] rather than \s: \s also matches line breaks and would eat the final newline.
$updated = [regex]::Replace($text, '(?m)^([ \t]*newName:[ \t]*).*$', "`${1}$name")
$updated = [regex]::Replace($updated, '(?m)^([ \t]*digest:[ \t]*)sha256:[0-9a-f]{64}[ \t]*$', "`${1}$digest")
if ($updated -notmatch [regex]::Escape($digest)) { throw "Could not find an images digest entry in $kustomization" }

if ($PSCmdlet.ShouldProcess($kustomization, "set image $name@$digest")) {
    [System.IO.File]::WriteAllText($kustomization, $updated)
    if (Test-Path (Join-Path $RepoRoot '.git')) { & git -C $RepoRoot --no-pager diff -- $kustomization }
    Write-Host "Promoted $digest to overlay '$Overlay'. Review, then commit with: git commit -m 'chore($Overlay): promote $($digest.Substring(7,12))'"
}
