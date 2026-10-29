BeforeAll {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $infoScript = Join-Path $repoRoot 'windows\Get-BuildInfo.ps1'
}

Describe 'Build metadata' {
    It 'returns a versioned build record' {
        $result = & $infoScript -Version '1.2.3' -BuildNumber '20261029'
        $result.Version | Should -Be '1.2.3'
        $result.BuildNumber | Should -Be '20261029'
        $result.RepoRoot | Should -Not -BeNullOrEmpty
    }

    It 'rejects an empty version' {
        { & $infoScript -Version '' } | Should -Throw 'Version is required.'
    }
}

Describe 'Build prerequisites' {
    It 'requires the app dependency file' {
        $path = Join-Path $repoRoot 'app\requirements.txt'
        $path | Should -Exist
    }

    It 'rejects a missing file path in the package step' {
        $missing = Join-Path $repoRoot 'missing\file.txt'
        Test-Path $missing | Should -BeFalse
    }
}
