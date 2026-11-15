<#
.SYNOPSIS
    Creates local throwaway branches that each break one security gate (spec item 17).
.DESCRIPTION
    Each branch holds one commit with one deliberate violation. Push a branch and open a pull
    request to watch the matching check turn red. Never merge these branches.

      gate-demo/fake-secret      Gitleaks       a random fake API key labelled as fake
      gate-demo/vuln-dependency  OSV-Scanner    jinja2 2.10 (known CVEs, confirm with osv-scanner)
      gate-demo/failing-test     pytest         a test that asserts the wrong status code
      gate-demo/unpinned-action  zizmor         a third-party action referenced by tag
      gate-demo/root-container   Trivy config   USER root in the Dockerfile

    Requires a clean working tree. Returns to the starting branch afterwards. -WhatIf lists the
    branches without creating anything. Commits use the configured Git identity, so the
    commit-msg hook applies.
.EXAMPLE
    pwsh -File scripts/make-gate-demos.ps1
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Write-Verbose "Repository root: $RepoRoot"

function Invoke-Git {
    param([string[]]$Arguments, [string]$Root = $script:RepoRoot)
    $out = & git -C $Root @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed: $($out -join ' ')" }
    return $out
}

# A random value generated at run time. It is not a credential for any service. Gitleaks ignores
# the AWS documentation example keys, so a random high-entropy value is used instead.
$alphabet = [char[]]'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
$fakeValue = -join (1..40 | ForEach-Object { $alphabet[[System.Security.Cryptography.RandomNumberGenerator]::GetInt32($alphabet.Length)] })

$demos = [ordered]@{
    'gate-demo/fake-secret' = @{
        Gate = 'Gitleaks'; Message = 'test(gate-demo): add fake credential for secret scan demo'
        Change = { Set-Content -LiteralPath (Join-Path $RepoRoot 'app/demo_settings.py') -Value "# FAKE value generated for a gate demonstration. Not a credential.`nDEMO_SERVICE_API_KEY = `"$fakeValue`"" }
    }
    'gate-demo/vuln-dependency' = @{
        Gate = 'OSV-Scanner'; Message = 'test(gate-demo): pin a known-vulnerable dependency'
        Change = { Add-Content -LiteralPath (Join-Path $RepoRoot 'app/requirements.txt') -Value 'jinja2==2.10' }
    }
    'gate-demo/failing-test' = @{
        Gate = 'pytest'; Message = 'test(gate-demo): add a deliberately failing test'
        Change = { Set-Content -LiteralPath (Join-Path $RepoRoot 'app/test_gate_demo.py') -Value "from app.test_main import client`n`n`ndef test_gate_demo_fails() -> None:`n    assert client.get('/health').status_code == 500`n" }
    }
    'gate-demo/unpinned-action' = @{
        Gate = 'zizmor'; Message = 'ci(gate-demo): reference a third-party action by tag'
        Change = { Set-Content -LiteralPath (Join-Path $RepoRoot '.github/workflows/gate-demo.yml') -Value "name: gate-demo`non: workflow_dispatch`npermissions: {}`njobs:`n  demo:`n    runs-on: ubuntu-24.04`n    steps:`n      - uses: aquasecurity/trivy-action@master`n" }
    }
    'gate-demo/root-container' = @{
        Gate = 'Trivy config'; Message = 'build(gate-demo): run the container as root'
        Change = {
            $df = Join-Path $RepoRoot 'Dockerfile'
            (Get-Content -LiteralPath $df -Raw).Replace('USER 65532:65532', 'USER root') | Set-Content -LiteralPath $df -NoNewline
        }
    }
}

if (-not $WhatIfPreference) {
    $status = Invoke-Git @('status', '--porcelain')
    if ($status) { throw 'Working tree is not clean. Commit or stash changes first.' }
}
$start = (Invoke-Git @('rev-parse', '--abbrev-ref', 'HEAD')) | Select-Object -First 1

try {
    foreach ($name in $demos.Keys) {
        $d = $demos[$name]
        if (-not $PSCmdlet.ShouldProcess($name, "create branch that should fail $($d.Gate)")) { continue }
        Invoke-Git @('switch', '-C', $name, $start) | Out-Null
        & $d.Change
        Invoke-Git @('add', '-A') | Out-Null
        Invoke-Git @('commit', '-q', '-m', $d.Message) | Out-Null
        Write-Host "Created $name (expected to fail: $($d.Gate))"
    }
}
finally {
    if (-not $WhatIfPreference) { Invoke-Git @('switch', $start) | Out-Null }
}
Write-Host "Push one with: git push -u origin gate-demo/fake-secret, then open a pull request. Never merge."
