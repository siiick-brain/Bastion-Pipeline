$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$files = Get-ChildItem -Path $repoRoot -Recurse -File |
    Where-Object {
        $_.FullName -notmatch [regex]::Escape((Join-Path $repoRoot '.git')) -and
        $_.FullName -notmatch [regex]::Escape((Join-Path $repoRoot '.venv')) -and
        $_.FullName -notmatch [regex]::Escape((Join-Path $repoRoot 'venv')) -and
        $_.FullName -notmatch [regex]::Escape((Join-Path $repoRoot 'node_modules')) -and
        $_.FullName -notmatch [regex]::Escape((Join-Path $repoRoot '.pytest_cache')) -and
        $_.FullName -notmatch [regex]::Escape((Join-Path $repoRoot '__pycache__')) -and
        $_.Extension -notin '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.pdf', '.zip'
    }

$failures = @()
$warnings = @()

foreach ($file in $files) {
    $relative = if ($file.FullName.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        $file.FullName.Substring($repoRoot.Length + 1)
    } else {
        $file.FullName
    }
    $content = Get-Content -Path $file.FullName -Raw -ErrorAction SilentlyContinue
    if ($null -eq $content) { continue }

    $inFence = $false
    $lines = $content -split "`r?`n"
    for ($i = 0; $i -lt $lines.Length; $i++) {
        $line = $lines[$i]

        if ($line -match '^```') {
            $inFence = -not $inFence
            continue
        }

        if ($inFence) { continue }

        
        if ($relative -ne 'scripts\check-style.ps1' -and $line -match '(?i)and,') {
            $failures += "FAIL: ${relative}:$($i + 1): contains 'and' followed by a comma"
        }

        if ($file.Extension -in '.md', '.txt', '.rst') {
            $isTableSeparator = $line -match '^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$'
            if (-not $isTableSeparator -and $line -match '(?<![A-Za-z0-9])--|—|–') {
                $failures += "FAIL: ${relative}:$($i + 1): contains a dash"
            }
        }




        if ($line -match ', and') {
            $warnings += "WARN: ${relative}:$($i + 1): comma before 'and'"
        }
    }
}

if ($failures.Count -gt 0) {
    foreach ($entry in $failures) { Write-Error $entry }
    exit 1
}

if ($warnings.Count -gt 0) {
    foreach ($entry in $warnings) { Write-Warning $entry }
}

Write-Host "Style check passed."
