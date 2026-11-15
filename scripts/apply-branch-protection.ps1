<#
.SYNOPSIS
    Shows, applies and verifies the main branch ruleset with the GitHub CLI.
.DESCRIPTION
    Dry run by default: prints the current ruleset and the intended one. Pass -Apply to change
    repository settings. -Apply asks for confirmation unless -Confirm:$false is passed, then
    reads the ruleset back and verifies every rule.

    Rules: block force pushes and deletion of main, require pull requests (0 approvals, so a
    sole maintainer is not locked out), require linear history and require the status checks
    in $RequiredChecks to pass. Repository admins can bypass only through a pull request.
.EXAMPLE
    pwsh -File scripts/apply-branch-protection.ps1
.EXAMPLE
    pwsh -File scripts/apply-branch-protection.ps1 -Apply
#>
[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
param(
    [string]$Repository = 'siiick-brain/Bastion-Pipeline',
    [string]$Branch = 'main',
    [string]$RulesetName = 'main-protection',
    [string[]]$RequiredChecks = @(
        'policy (authorship, style, workflow and config lint)',
        'build-test / lint-and-test',
        'container (build, runtime tests, image scan)',
        'manifests (kustomize, kubeconform, Trivy config)',
        'windows-build',
        'SAST (Semgrep)',
        'Secrets (Gitleaks, full history)',
        'SCA gate (OSV-Scanner on lock files)',
        'IaC and filesystem (Trivy config and fs secrets)'
    ),
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Repository -notmatch '^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$') { throw "Invalid repository: $Repository" }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'GitHub CLI (gh) is required.' }

function Invoke-Gh {
    param([string[]]$Arguments, [string]$InputJson)
    $out = if ($InputJson) { $InputJson | & gh @Arguments 2>&1 } else { & gh @Arguments 2>&1 }
    if ($LASTEXITCODE -ne 0) { throw "gh $($Arguments -join ' ') failed: $($out -join ' ')" }
    return ($out -join "`n")
}

$desired = [ordered]@{
    name        = $RulesetName
    target      = 'branch'
    enforcement = 'active'
    conditions  = @{ ref_name = @{ include = @("refs/heads/$Branch"); exclude = @() } }
    bypass_actors = @(@{ actor_id = 5; actor_type = 'RepositoryRole'; bypass_mode = 'pull_request' })
    rules       = @(
        @{ type = 'deletion' },
        @{ type = 'non_fast_forward' },
        @{ type = 'required_linear_history' },
        @{ type = 'pull_request'; parameters = @{
                required_approving_review_count = 0; dismiss_stale_reviews_on_push = $true
                require_code_owner_review = $false; require_last_push_approval = $false
                required_review_thread_resolution = $true } },
        @{ type = 'required_status_checks'; parameters = @{
                strict_required_status_checks_policy = $true
                required_status_checks = @($RequiredChecks | ForEach-Object { @{ context = $_ } }) } }
    )
}
$desiredJson = $desired | ConvertTo-Json -Depth 10

$existing = (Invoke-Gh @('api', "repos/$Repository/rulesets")) | ConvertFrom-Json
$current = $existing | Where-Object { $_.name -eq $RulesetName } | Select-Object -First 1

Write-Host "Repository: $Repository  Branch: $Branch"
if ($current) {
    $full = Invoke-Gh @('api', "repos/$Repository/rulesets/$($current.id)")
    Write-Host "Current ruleset '$RulesetName' (id $($current.id)):"
    Write-Host $full
} else {
    Write-Host "No ruleset named '$RulesetName' exists."
}
Write-Host "Intended ruleset:"
Write-Host $desiredJson

if (-not $Apply) {
    Write-Host 'Dry run only. Re-run with -Apply to change repository settings.'
    return
}

$action = if ($current) { "update ruleset $($current.id)" } else { 'create ruleset' }
if (-not $PSCmdlet.ShouldProcess("$Repository ($Branch)", $action)) { Write-Host 'Cancelled.'; return }

if ($current) {
    $result = Invoke-Gh @('api', '--method', 'PUT', "repos/$Repository/rulesets/$($current.id)", '--input', '-') $desiredJson
} else {
    $result = Invoke-Gh @('api', '--method', 'POST', "repos/$Repository/rulesets", '--input', '-') $desiredJson
}
$id = ($result | ConvertFrom-Json).id

$applied = (Invoke-Gh @('api', "repos/$Repository/rulesets/$id")) | ConvertFrom-Json
$types = @($applied.rules | ForEach-Object type)
$missing = @('deletion', 'non_fast_forward', 'required_linear_history', 'pull_request', 'required_status_checks') |
    Where-Object { $types -notcontains $_ }
$checks = @(($applied.rules | Where-Object type -EQ 'required_status_checks').parameters.required_status_checks.context)
$missingChecks = @($RequiredChecks | Where-Object { $checks -notcontains $_ })
if ($applied.enforcement -ne 'active' -or $missing -or $missingChecks) {
    throw "Verification FAILED: enforcement=$($applied.enforcement) missing rules=[$($missing -join ',')] missing checks=[$($missingChecks -join ',')]"
}
Write-Host "Verified: ruleset $id is active with $($types.Count) rules and $($checks.Count) required checks."
