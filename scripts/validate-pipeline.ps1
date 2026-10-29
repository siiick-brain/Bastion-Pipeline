param(
    [switch]$SkipStyle
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

Write-Host 'Validating repo guardrails...'
if (-not $SkipStyle) {
    & (Join-Path $repoRoot 'scripts/check-style.ps1')
}

Write-Host 'Validating workflow YAML...'
python -c "import pathlib,yaml; files=sorted(pathlib.Path('.github/workflows').glob('*.yml')); [yaml.safe_load(open(f, 'r', encoding='utf-8')) for f in files]; print('workflow yaml ok')"

Write-Host 'Running app tests...'
python -m pytest app/test_main.py -q

if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host 'Running Docker build check...'
    docker build -t bastion-pipeline:local .
} else {
    Write-Warning 'Docker not available; skipped local image build.'
}

Write-Host 'Pipeline validation completed.'
