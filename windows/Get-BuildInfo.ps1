param(
    [string]$Version = '0.1.0',
    [string]$BuildNumber = (Get-Date -Format 'yyyyMMddHHmmss')
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Version)) {
    throw 'Version is required.'
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$branch = ''
$commit = ''

if (Get-Command git -ErrorAction SilentlyContinue) {
    try {
        $branch = (& git -C $repoRoot rev-parse --abbrev-ref HEAD 2>$null)
        $commit = (& git -C $repoRoot rev-parse --short HEAD 2>$null)
    } catch {
        $branch = ''
        $commit = ''
    }
}

[pscustomobject]@{
    Version = $Version
    BuildNumber = $BuildNumber
    TimestampUtc = (Get-Date).ToUniversalTime().ToString('o')
    Branch = $branch
    Commit = $commit
    RepoRoot = $repoRoot
}
