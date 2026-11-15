[Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSUseDeclaredVarsMoreThanAssignments', '', Justification = 'Variables are set in BeforeAll and BeforeEach and read in It blocks.')]
[Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSUseShouldProcessForStateChangingFunctions', '', Justification = 'Test helper writes only inside TestDrive.')]
param()

BeforeAll {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $infoScript = Join-Path $repoRoot 'windows\Get-BuildInfo.ps1'
    $buildScript = Join-Path $repoRoot 'windows\build.ps1'
    $batScript = Join-Path $repoRoot 'windows\build.bat'
    Import-Module (Join-Path $repoRoot 'windows\BastionBuild.psm1') -Force

    function New-FakeRepo {
        param([string]$Root)
        foreach ($rel in Get-PackageFileList) {
            $p = Join-Path $Root $rel
            New-Item -ItemType Directory -Path (Split-Path -Parent $p) -Force | Out-Null
            Set-Content -LiteralPath $p -Value "content of $rel"
        }
    }
    function Get-StagingDir { @(Get-ChildItem ([System.IO.Path]::GetTempPath()) -Directory -Filter 'bastion-stage-*' -ErrorAction SilentlyContinue) }
}

Describe 'Build metadata' {
    It 'returns a versioned build record' {
        $result = & $infoScript -Version '1.2.3' -BuildNumber '20261029'
        $result.Version | Should -Be '1.2.3'
        $result.BuildNumber | Should -Be '20261029'
        $result.Commit | Should -Match '^([0-9a-f]{40})?$'
    }
    It 'rejects an empty version' {
        { & $infoScript -Version '' } | Should -Throw 'Version is required.'
    }
    It 'does not leak absolute paths' {
        $json = & $infoScript -Version '1.0.0' -BuildNumber '1' | ConvertTo-Json
        $json | Should -Not -Match ([regex]::Escape($repoRoot))
        $json | Should -Not -Match 'RepoRoot'
    }
}

Describe 'Argument validation' {
    It 'accepts <v>' -ForEach @(@{ v = '0.1.0' }, @{ v = '10.20.30' }, @{ v = '1.0.0-rc.1' }) {
        { Assert-BuildVersion -Version $v } | Should -Not -Throw
    }
    It 'rejects version <v>' -ForEach @(@{ v = '' }, @{ v = '1.0' }, @{ v = 'v1.0.0' }, @{ v = '1.0.0;rm' }, @{ v = '../1.0.0' }) {
        { Assert-BuildVersion -Version $v } | Should -Throw '*Invalid version*'
    }
    It 'rejects build number <b>' -ForEach @(@{ b = '' }, @{ b = 'abc' }, @{ b = '1 2' }, @{ b = ('9' * 21) }) {
        { Assert-BuildNumber -BuildNumber $b } | Should -Throw '*Invalid build number*'
    }
}

Describe 'Prerequisites' {
    It 'fails clearly when a module is missing' {
        { Assert-Prerequisite -ModuleName 'Bastion.NoSuchModule' -MinimumVersion 1.0.0 } |
            Should -Throw '*Missing prerequisite: Bastion.NoSuchModule*Install-Module*'
    }
    It 'fails when only an older version is present' {
        { Assert-Prerequisite -ModuleName 'Microsoft.PowerShell.Utility' -MinimumVersion 99.0.0 } | Should -Throw '*Missing prerequisite*'
    }
}

Describe 'Packaging' {
    BeforeEach {
        $root = Join-Path $TestDrive 'repo with spaces'
        $out = Join-Path $TestDrive ("out dir with spaces " + [guid]::NewGuid().ToString('N'))
        New-FakeRepo -Root $root
        $pkg = Join-Path $out 'pkg 1.zip'
    }
    It 'creates a zip with exactly the expected files under paths with spaces' {
        New-BuildPackage -RepoRoot $root -DestinationPath $pkg
        $pkg | Should -Exist
        { Test-PackageContent -PackagePath $pkg } | Should -Not -Throw
        "$pkg.partial" | Should -Not -Exist
    }
    It 'fails on a missing input file and leaves no package' {
        Remove-Item (Join-Path $root 'app/main.py')
        { New-BuildPackage -RepoRoot $root -DestinationPath $pkg } | Should -Throw '*Missing input file: app/main.py*'
        $pkg | Should -Not -Exist
    }
    It 'cleans up the staging folder when packaging fails' {
        $before = @(Get-StagingDir).Count
        Mock -ModuleName BastionBuild Test-PackageContent { throw 'simulated interruption' }
        { New-BuildPackage -RepoRoot $root -DestinationPath $pkg } | Should -Throw '*simulated interruption*'
        @(Get-StagingDir).Count | Should -Be $before
        $pkg | Should -Not -Exist
        "$pkg.partial" | Should -Not -Exist
    }
    It 'detects unexpected extra content in a package' {
        New-BuildPackage -RepoRoot $root -DestinationPath $pkg
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $z = [System.IO.Compression.ZipFile]::Open($pkg, 'Update')
        try { [void]$z.CreateEntry('evil.ps1') } finally { $z.Dispose() }
        { Test-PackageContent -PackagePath $pkg } | Should -Throw '*Package content mismatch*evil.ps1*'
    }
}

Describe 'Checksums' {
    BeforeEach {
        $dir = Join-Path $TestDrive 'sums dir'
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        $file = Join-Path $dir 'pkg.zip'
        Set-Content -LiteralPath $file -Value 'payload'
        $sums = Join-Path $dir 'SHA256SUMS'
    }
    It 'writes lowercase sha256sum format and verifies' {
        $hash = Write-Checksum -PackagePath $file -ChecksumPath $sums
        $hash | Should -Match '^[0-9a-f]{64}$'
        (Get-Content $sums) | Should -Be "$hash  pkg.zip"
        Test-Checksum -ChecksumPath $sums | Should -BeTrue
    }
    It 'detects a modified package' {
        Write-Checksum -PackagePath $file -ChecksumPath $sums | Out-Null
        Add-Content -LiteralPath $file -Value 'tampered'
        Test-Checksum -ChecksumPath $sums | Should -BeFalse
    }
    It 'detects a missing package' {
        Write-Checksum -PackagePath $file -ChecksumPath $sums | Out-Null
        Remove-Item $file
        Test-Checksum -ChecksumPath $sums | Should -BeFalse
    }
    It 'rejects a malformed line' {
        Set-Content $sums 'not-a-hash  pkg.zip'
        { Test-Checksum -ChecksumPath $sums } | Should -Throw '*Malformed*'
    }
    It 'rejects path traversal in a checksum entry' {
        Set-Content $sums "$('a' * 64)  ..\outside.zip"
        { Test-Checksum -ChecksumPath $sums } | Should -Throw '*Unsafe file name*'
    }
    It 'rejects an empty or missing checksum file' {
        Set-Content $sums ''
        { Test-Checksum -ChecksumPath $sums } | Should -Throw '*empty*'
        { Test-Checksum -ChecksumPath (Join-Path $dir 'nope') } | Should -Throw '*not found*'
    }
}

Describe 'Entry points and exit codes' {
    [Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSUseDeclaredVarsMoreThanAssignments', '', Justification = 'Variables are set in BeforeAll and BeforeEach and read in It blocks.')]
[Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSUseShouldProcessForStateChangingFunctions', '', Justification = 'Test helper writes only inside TestDrive.')]
param()

BeforeAll {
        $pwshExe = (Get-Process -Id $PID).Path
        $outDir = Join-Path $TestDrive 'e2e out'
    }
    It 'build.ps1 succeeds from an unrelated working directory' {
        Push-Location $TestDrive
        try {
            & $pwshExe -NoProfile -File $buildScript -Version 1.2.3 -BuildNumber 7 -OutputDir $outDir -SkipChecks | Out-Null
            $LASTEXITCODE | Should -Be 0
        } finally { Pop-Location }
        Join-Path $outDir 'bastion-pipeline_1.2.3_7.zip' | Should -Exist
        Test-Checksum -ChecksumPath (Join-Path $outDir 'SHA256SUMS') | Should -BeTrue
    }
    It 'build.ps1 exits non-zero on an invalid version' {
        & $pwshExe -NoProfile -File $buildScript -Version 'bad' -OutputDir $outDir -SkipChecks *> $null
        $LASTEXITCODE | Should -Not -Be 0
    }
    It 'build.bat propagates a failing exit code' -Skip:(-not $IsWindows) {
        & cmd.exe /d /c "`"$batScript`" -Version bad -SkipChecks" *> $null
        $LASTEXITCODE | Should -Not -Be 0
    }
    It 'build.bat propagates success' -Skip:(-not $IsWindows) {
        & cmd.exe /d /c "`"$batScript`" -Version 1.0.0 -BuildNumber 1 -SkipChecks -OutputDir `"$outDir`"" *> $null
        $LASTEXITCODE | Should -Be 0
    }
}
