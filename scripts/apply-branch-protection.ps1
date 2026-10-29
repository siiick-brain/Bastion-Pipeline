param(
    [string]$Repository = $env:GITHUB_REPOSITORY,
    [string]$Branch = 'main',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

if (-not $Repository) {
    $Repository = git remote get-url origin 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($Repository)) {
        throw 'A GitHub repository is required. Set -Repository or configure origin.'
    }
    $Repository = $Repository -replace '.*github.com[:/]','' -replace '\.git$',''
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'GitHub CLI not found. Install gh to enforce branch protection.'
}

$body = @{
    required_status_checks = @{ strict = $true; contexts = @('build-test'); }
    enforce_admins = $true
    required_pull_request_reviews = @{ required_approving_review_count = 1; dismiss_stale_reviews = $true; require_code_owner_reviews = $true }
    restrictions = $null
    required_linear_history = $true
    allow_force_pushes = $false
    allow_deletions = $false
    block_creations = $false
    required_conversation_resolution = $true
} | ConvertTo-Json -Depth 8

if ($DryRun) {
    Write-Host "Dry run: gh api repos/$Repository/branches/$Branch/protection --method PUT --input -"
    Write-Host $body
    return
}

$null = gh api "repos/$Repository/branches/$Branch/protection" --method PUT --input - <<< $body
Write-Host "Branch protection applied for $Repository:$Branch."
