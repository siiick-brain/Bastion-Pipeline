param(
    [string]$OutputDir = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path 'artifacts/screenshots')
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$files = @(
    'ci-success.png',
    'security-scan.png',
    'release-signing.png',
    'gitops-diff.png'
)

foreach ($file in $files) {
    $path = Join-Path $OutputDir $file
    Set-Content -Path $path -Value "Placeholder proof artifact for $file" -Encoding UTF8
    Write-Host "Prepared: $path"
}

Write-Host "Screenshot prep complete in $OutputDir."
