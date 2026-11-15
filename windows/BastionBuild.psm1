Set-StrictMode -Version Latest

$script:PackageFiles = @(
    'app/__init__.py',
    'app/main.py',
    'app/requirements.txt',
    'windows/Get-BuildInfo.ps1',
    'README.md',
    'LICENSE'
)

function Assert-BuildVersion {
    [CmdletBinding()]
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Version)
    if ($Version -notmatch '^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$') {
        throw "Invalid version '$Version'. Expected semantic version such as 1.2.3."
    }
}

function Assert-BuildNumber {
    [CmdletBinding()]
    param([Parameter(Mandatory)][AllowEmptyString()][string]$BuildNumber)
    if ($BuildNumber -notmatch '^[0-9]{1,20}$') {
        throw "Invalid build number '$BuildNumber'. Expected 1 to 20 digits."
    }
}

function Assert-Prerequisite {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$ModuleName,
        [Parameter(Mandatory)][version]$MinimumVersion
    )
    $found = Get-Module -ListAvailable -Name $ModuleName | Where-Object Version -GE $MinimumVersion
    if (-not $found) {
        throw "Missing prerequisite: $ModuleName $MinimumVersion or later. Install with: Install-Module $ModuleName -RequiredVersion $MinimumVersion -Scope CurrentUser"
    }
}

function Get-PackageFileList {
    [CmdletBinding()]
    [OutputType([string[]])]
    param()
    return $script:PackageFiles
}

function New-BuildPackage {
    <#
    .SYNOPSIS
        Stages the package files in a temporary folder and writes the zip atomically.
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$DestinationPath
    )
    if (-not $PSCmdlet.ShouldProcess($DestinationPath, 'create package')) { return }
    foreach ($rel in $script:PackageFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $rel) -PathType Leaf)) {
            throw "Missing input file: $rel"
        }
    }
    $destDir = Split-Path -Parent $DestinationPath
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    $staging = Join-Path ([System.IO.Path]::GetTempPath()) ("bastion-stage-" + [guid]::NewGuid().ToString('N'))
    $partial = "$DestinationPath.partial"
    try {
        foreach ($rel in $script:PackageFiles) {
            $target = Join-Path $staging $rel
            New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
            Copy-Item -LiteralPath (Join-Path $RepoRoot $rel) -Destination $target
        }
        if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::CreateFromDirectory($staging, $partial)
        Test-PackageContent -PackagePath $partial
        Move-Item -LiteralPath $partial -Destination $DestinationPath -Force
    }
    finally {
        if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
        if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
    }
}

function Test-PackageContent {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$PackagePath)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($PackagePath)
    try {
        $entries = @($zip.Entries | Where-Object { $_.Name } | ForEach-Object { $_.FullName.Replace('\', '/') } | Sort-Object)
    }
    finally { $zip.Dispose() }
    $expected = @($script:PackageFiles | Sort-Object)
    $diff = Compare-Object -ReferenceObject $expected -DifferenceObject $entries
    if ($diff) {
        throw "Package content mismatch: $(($diff | ForEach-Object { "$($_.SideIndicator)$($_.InputObject)" }) -join ', ')"
    }
}

function Write-Checksum {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$PackagePath,
        [Parameter(Mandatory)][string]$ChecksumPath
    )
    $hash = (Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $line = "$hash  $(Split-Path -Leaf $PackagePath)"
    [System.IO.File]::WriteAllText($ChecksumPath, "$line`n")
    return $hash
}

function Test-Checksum {
    <#
    .SYNOPSIS
        Verifies every entry of a sha256sum-format file. Returns $true only when all match.
    #>
    [CmdletBinding()]
    [OutputType([bool])]
    param([Parameter(Mandatory)][string]$ChecksumPath)
    if (-not (Test-Path -LiteralPath $ChecksumPath)) { throw "Checksum file not found: $ChecksumPath" }
    $dir = Split-Path -Parent $ChecksumPath
    $lines = @(Get-Content -LiteralPath $ChecksumPath | Where-Object { $_.Trim() })
    if ($lines.Count -eq 0) { throw "Checksum file is empty: $ChecksumPath" }
    foreach ($line in $lines) {
        if ($line -notmatch '^([0-9a-f]{64}) [ *](.+)$') { throw "Malformed checksum line: $line" }
        $expected = $Matches[1]
        $name = $Matches[2]
        if ($name -match '[\\/]|\.\.') { throw "Unsafe file name in checksum file: $name" }
        $file = Join-Path $dir $name
        if (-not (Test-Path -LiteralPath $file)) { return $false }
        $actual = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $expected) { return $false }
    }
    return $true
}

Export-ModuleMember -Function Assert-BuildVersion, Assert-BuildNumber, Assert-Prerequisite, Get-PackageFileList,
    New-BuildPackage, Test-PackageContent, Write-Checksum, Test-Checksum
