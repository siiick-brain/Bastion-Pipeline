<#
.SYNOPSIS
    Enforces docs/STYLE.md punctuation rules on prose files.
.DESCRIPTION
    Checks tracked Markdown and text files (or the files given with -Path).
    Code fences, inline code and table separator rows are skipped.
    Exceptions live in .style-allow as "<path glob>|<rule id>|<reason>".
    Exit code 0 when clean, 1 when any rule fails, 2 on usage errors.
.EXAMPLE
    pwsh -File scripts/check-style.ps1
.EXAMPLE
    pwsh -File scripts/check-style.ps1 -Path tests/style/bad.md
#>
[CmdletBinding()]
param(
    [string[]]$Path,
    [string]$AllowFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $AllowFile) { $AllowFile = Join-Path $repoRoot '.style-allow' }

$rules = @(
    @{ Id = 'dash';        Pattern = '[\u2014\u2013]'; Message = 'em or en dash' }
    @{ Id = 'double-dash'; Pattern = '(?<![\w-])--(?![\w-])';   Message = 'double hyphen used as a dash' }
    @{ Id = 'and-comma';   Pattern = '(?i)\band,';              Message = "'and' followed by a comma" }
    @{ Id = 'comma-and';   Pattern = '(?i),\s+and\b';           Message = "comma before 'and'" }
    @{ Id = 'comma-or';    Pattern = '(?i),\s+or\b';            Message = "comma before 'or'" }
)

function Get-AllowList {
    param([string]$File)
    $entries = @()
    if (-not (Test-Path -LiteralPath $File)) { return $entries }
    foreach ($raw in Get-Content -LiteralPath $File) {
        $line = $raw.Trim()
        if (-not $line -or $line.StartsWith('#')) { continue }
        $parts = $line.Split('|')
        if ($parts.Count -lt 3 -or -not $parts[2].Trim()) {
            throw "Invalid .style-allow entry (need path|rule|reason): $line"
        }
        $entries += @{ Glob = $parts[0].Trim(); Rule = $parts[1].Trim() }
    }
    return $entries
}

function Test-Allowed {
    param([string]$Relative, [string]$RuleId, [object[]]$Allow)
    foreach ($entry in $Allow) {
        if ($Relative -like $entry.Glob -and ($entry.Rule -eq '*' -or $entry.Rule -eq $RuleId)) { return $true }
    }
    return $false
}

function Get-TargetFile {
    param([string[]]$Target)
    if ($Target) {
        foreach ($p in $Target) {
            if (-not (Test-Path -LiteralPath $p)) { Write-Error "File not found: $p" -ErrorAction Continue; exit 2 }
            (Resolve-Path -LiteralPath $p).Path
        }
        return
    }
    $tracked = & git -C $repoRoot ls-files -- '*.md' '*.txt'
    if ($LASTEXITCODE -ne 0) { Write-Error 'git ls-files failed' -ErrorAction Continue; exit 2 }
    foreach ($rel in $tracked) {
        $full = Join-Path $repoRoot $rel
        if (Test-Path -LiteralPath $full) { $full }
    }
}

$allow = Get-AllowList -File $AllowFile
$failures = [System.Collections.Generic.List[string]]::new()

foreach ($file in Get-TargetFile -Target $Path) {
    $relative = [System.IO.Path]::GetRelativePath($repoRoot, $file).Replace('\', '/')
    $inFence = $false
    $lineNo = 0
    foreach ($line in [System.IO.File]::ReadAllLines($file)) {
        $lineNo++
        if ($line -match '^\s*(```|~~~)') { $inFence = -not $inFence; continue }
        if ($inFence) { continue }
        if ($line -match '^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$') { continue }
        $prose = $line -replace '`[^`]*`', 'CODE' -replace '<!--.*?-->', '' -replace '\]\([^)]*\)', ']'
        foreach ($rule in $rules) {
            if ($prose -match $rule.Pattern -and -not (Test-Allowed -Relative $relative -RuleId $rule.Id -Allow $allow)) {
                $failures.Add("${relative}:${lineNo}: [$($rule.Id)] $($rule.Message)")
            }
        }
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Host "FAIL $_" }
    Write-Host "Style check failed: $($failures.Count) finding(s). See docs/STYLE.md."
    exit 1
}
Write-Host 'Style check passed.'
exit 0
