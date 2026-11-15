<#
.SYNOPSIS
    Returns build metadata. Contains no absolute paths so it is safe to ship.
#>
[CmdletBinding()]
param(
    [string]$Version = '0.1.0',
    [string]$BuildNumber = (Get-Date -Format 'yyyyMMddHHmmss')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Version)) {
    throw 'Version is required.'
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$branch = ''
$commit = ''

if (Get-Command git -ErrorAction SilentlyContinue) {
    $branch = (& git -C $repoRoot rev-parse --abbrev-ref HEAD 2>$null)
    if ($LASTEXITCODE -ne 0) { $branch = '' }
    $commit = (& git -C $repoRoot rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0) { $commit = '' }
}

[pscustomobject]@{
    Version      = $Version
    BuildNumber  = $BuildNumber
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
    Branch       = "$branch"
    Commit       = "$commit"
}
