<#
.SYNOPSIS
    Lints, tests and packages the Windows deliverable.
.DESCRIPTION
    1. Validates arguments and prerequisites (no silent installs).
    2. Runs PSScriptAnalyzer with PSScriptAnalyzerSettings.psd1 and fails on any finding.
    3. Runs the Pester suites and fails on any test failure.
    4. Creates the zip atomically, verifies its contents and writes SHA256SUMS.
    Exit code 0 on success, 1 on any failure.
.EXAMPLE
    pwsh -File windows/build.ps1 -Version 0.1.0 -BuildNumber 42
#>
[CmdletBinding()]
param(
    [string]$Version = '0.1.0',
    [string]$BuildNumber = (Get-Date -Format 'yyyyMMddHHmmss'),
    [string]$OutputDir = (Join-Path $PSScriptRoot '..\artifacts\windows'),
    [switch]$SkipChecks
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Import-Module (Join-Path $PSScriptRoot 'BastionBuild.psm1') -Force

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Assert-BuildVersion -Version $Version
Assert-BuildNumber -BuildNumber $BuildNumber

if (-not $SkipChecks) {
    Assert-Prerequisite -ModuleName PSScriptAnalyzer -MinimumVersion 1.25.0
    Assert-Prerequisite -ModuleName Pester -MinimumVersion 5.5.0
    Import-Module PSScriptAnalyzer
    Import-Module Pester -MinimumVersion 5.5.0

    $settings = Join-Path $repoRoot 'PSScriptAnalyzerSettings.psd1'
    $findings = foreach ($dir in 'windows', 'scripts', 'tests') {
        Invoke-ScriptAnalyzer -Path (Join-Path $repoRoot $dir) -Recurse -Settings $settings
    }
    if ($findings) {
        $findings | Format-Table -AutoSize RuleName, Severity, ScriptName, Line, Message | Out-String | Write-Host
        throw "PSScriptAnalyzer reported $(@($findings).Count) finding(s)."
    }
    Write-Host 'PSScriptAnalyzer: no findings.'

    $config = New-PesterConfiguration
    $config.Run.Path = @((Join-Path $repoRoot 'windows/tests'), (Join-Path $repoRoot 'tests/style'))
    $config.Run.PassThru = $true
    $config.Output.Verbosity = 'Detailed'
    $config.TestResult.Enabled = $true
    $config.TestResult.OutputPath = Join-Path ([System.IO.Path]::GetFullPath($OutputDir)) 'pester-results.xml'
    New-Item -ItemType Directory -Path ([System.IO.Path]::GetFullPath($OutputDir)) -Force | Out-Null
    $result = Invoke-Pester -Configuration $config
    if ($result.FailedCount -gt 0 -or $result.Result -ne 'Passed') {
        throw "Pester failed: $($result.FailedCount) failed test(s)."
    }
}

$artifactRoot = [System.IO.Path]::GetFullPath($OutputDir)
$packageName = "bastion-pipeline_${Version}_${BuildNumber}.zip"
$packagePath = Join-Path $artifactRoot $packageName
New-BuildPackage -RepoRoot $repoRoot -DestinationPath $packagePath
$hash = Write-Checksum -PackagePath $packagePath -ChecksumPath (Join-Path $artifactRoot 'SHA256SUMS')
if (-not (Test-Checksum -ChecksumPath (Join-Path $artifactRoot 'SHA256SUMS'))) {
    throw 'Checksum verification failed immediately after writing.'
}

$buildInfo = & (Join-Path $PSScriptRoot 'Get-BuildInfo.ps1') -Version $Version -BuildNumber $BuildNumber
$buildInfo | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $artifactRoot 'build-info.json') -Encoding utf8

Write-Host "Package: $packagePath"
Write-Host "SHA256:  $hash"
