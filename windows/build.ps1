param(
    [string]$Version = '0.1.0',
    [string]$BuildNumber = (Get-Date -Format 'yyyyMMddHHmmss'),
    [string]$OutputDir = (Join-Path $PSScriptRoot '..\artifacts')
)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$artifactRoot = [System.IO.Path]::GetFullPath($OutputDir)
$packageName = "bastion-pipeline_${Version}_${BuildNumber}.zip"
$packagePath = Join-Path $artifactRoot $packageName
$checksumsPath = Join-Path $artifactRoot 'SHA256SUMS'

New-Item -ItemType Directory -Path $artifactRoot -Force | Out-Null

if (-not (Test-Path (Join-Path $repoRoot 'app\requirements.txt'))) {
    throw 'Missing app dependency file.'
}

if (-not (Get-Command Invoke-ScriptAnalyzer -ErrorAction SilentlyContinue)) {
    Install-Module PSScriptAnalyzer -Scope CurrentUser -Force -SkipPublisherCheck -ErrorAction Stop
}

Invoke-ScriptAnalyzer -Path (Join-Path $repoRoot 'windows'), (Join-Path $repoRoot 'scripts') -Recurse

if (-not (Get-Command Invoke-Pester -ErrorAction SilentlyContinue)) {
    Install-Module Pester -Scope CurrentUser -Force -SkipPublisherCheck -ErrorAction Stop
}

if (-not (Test-Path (Join-Path $repoRoot 'windows\tests\build.tests.ps1'))) {
    throw 'Missing Pester suite.'
}

Invoke-Pester -Path (Join-Path $repoRoot 'windows\tests\build.tests.ps1') -Output Detailed

$zipInput = @(
    (Join-Path $repoRoot 'app'),
    (Join-Path $repoRoot 'windows'),
    (Join-Path $repoRoot 'README.md'),
    (Join-Path $repoRoot 'LICENSE')
)

Compress-Archive -Path $zipInput -DestinationPath $packagePath -Force

$hash = (Get-FileHash -Path $packagePath -Algorithm SHA256).Hash
Set-Content -Path $checksumsPath -Value "$hash  $packageName"

$buildInfo = & (Join-Path $PSScriptRoot 'Get-BuildInfo.ps1') -Version $Version -BuildNumber $BuildNumber

Write-Host "Package: $packagePath"
Write-Host "SHA256: $hash"
Write-Host "Build info: $($buildInfo | ConvertTo-Json -Compress)"
