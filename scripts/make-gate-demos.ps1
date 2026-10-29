param(
    [switch]$Create
)

$branches = @(
    'gate-demo/failing-lint',
    'gate-demo/failing-security',
    'gate-demo/failing-tests'
)

if (-not $Create) {
    foreach ($branch in $branches) {
        Write-Host "Suggested demo branch: $branch"
    }
    Write-Host 'Run with -Create to create the branches locally.'
    return
}

foreach ($branch in $branches) {
    git checkout -b $branch *> $null
    Write-Host "Created branch: $branch"
    git checkout - *> $null
}

Write-Host 'Demo branches created. Remove them after you finish the gate demonstrations.'
