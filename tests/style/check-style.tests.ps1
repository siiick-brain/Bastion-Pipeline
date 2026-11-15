[Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSUseDeclaredVarsMoreThanAssignments', '', Justification = 'Variables are set in BeforeAll and BeforeEach and read in It blocks.')]
param()

BeforeAll {
    $script = Join-Path $PSScriptRoot '../../scripts/check-style.ps1'
    $good = Join-Path $PSScriptRoot 'good.md'
    $bad = Join-Path $PSScriptRoot 'bad.md'
    $emptyAllow = Join-Path $TestDrive 'none.allow'
    function Invoke-Style { param([string[]]$Arguments) $out = & pwsh -NoProfile -File $script @Arguments 2>&1; [pscustomobject]@{ Code = $LASTEXITCODE; Out = ($out -join "`n") } }
}

Describe 'check-style.ps1' {
    It 'passes the good fixture' {
        (Invoke-Style -Arguments @('-Path', $good, '-AllowFile', $emptyAllow)).Code | Should -Be 0
    }
    It 'fails the bad fixture with every rule' {
        $r = Invoke-Style -Arguments @('-Path', $bad, '-AllowFile', $emptyAllow)
        $r.Code | Should -Be 1
        foreach ($id in 'dash', 'comma-and', 'and-comma', 'comma-or', 'double-dash') { $r.Out | Should -Match "\[$id\]" }
    }
    It 'honours an allow entry with a reason' {
        $allow = Join-Path $TestDrive 'ok.allow'
        Set-Content $allow 'tests/style/bad.md|*|fixture is intentionally bad'
        (Invoke-Style -Arguments @('-Path', $bad, '-AllowFile', $allow)).Code | Should -Be 0
    }
    It 'rejects an allow entry without a reason' {
        $allow = Join-Path $TestDrive 'noreason.allow'
        Set-Content $allow 'tests/style/bad.md|*|'
        (Invoke-Style -Arguments @('-Path', $bad, '-AllowFile', $allow)).Code | Should -Not -Be 0
    }
    It 'returns 2 for a missing file' {
        (Invoke-Style -Arguments @('-Path', (Join-Path $TestDrive 'missing.md'))).Code | Should -Be 2
    }
    It 'passes on the repository itself' {
        (Invoke-Style -Arguments @()).Code | Should -Be 0
    }
}
