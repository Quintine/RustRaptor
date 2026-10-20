# Native Windows PowerShell 5.1 synthetic ZIP/install smoke test. No game build,
# network download, admin rights or long-path registry configuration is needed.
param([string]$Installer = (Join-Path $PSScriptRoot 'Install-Windows.ps1'))
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$temp = Join-Path ([IO.Path]::GetTempPath()) ('Raptor-installer-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
$global:RaptorInstallerFixtureDownloads = Join-Path $temp 'downloads'
New-Item -ItemType Directory -Path $global:RaptorInstallerFixtureDownloads | Out-Null
function global:Invoke-WebRequest {
    param([switch]$UseBasicParsing, [string]$Uri, [string]$OutFile)
    $leaf = [IO.Path]::GetFileName(([Uri]$Uri).AbsolutePath)
    Copy-Item -LiteralPath (Join-Path $global:RaptorInstallerFixtureDownloads $leaf) -Destination $OutFile
}
function New-FixtureArchive([string]$Name, [string]$Kind, [string]$Member) {
    $path = Join-Path $global:RaptorInstallerFixtureDownloads $Name
    $body = [Text.Encoding]::UTF8.GetBytes('synthetic payload ' + $Member)
    $zip = [IO.Compression.ZipFile]::Open($path, [IO.Compression.ZipArchiveMode]::Create)
    try {
        $entry = $zip.CreateEntry('RustRaptor/' + $Member)
        $entry.ExternalAttributes = (0x81A4 -shl 16)
        $stream = $entry.Open()
        try { $stream.Write($body, 0, $body.Length) } finally { $stream.Dispose() }
    } finally { $zip.Dispose() }
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $payloadHash = [BitConverter]::ToString($sha.ComputeHash($body)).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
    return @{ name=$Name; kind=$Kind; bytes=(Get-Item -LiteralPath $path).Length;
              sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant();
              files=@(@{name=$Member; bytes=$body.Length; sha256=$payloadHash}) }
}
try {
    $longMember = 'data/' + (('long-proof-component/' * 20)) + 'accepted.json'
    $data = New-FixtureArchive 'RustRaptor-data-01-of-01.zip' 'shared-data' $longMember
    $core = New-FixtureArchive 'RustRaptor-windows-x86_64.zip' 'windows' 'run.cmd'
    $manifest = @{format_version=1; tag='v0.1.0-preview.20261020'; assets=@($data, $core)}
    $manifestPath = Join-Path $global:RaptorInstallerFixtureDownloads 'release-manifest.json'
    $manifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    $destination = Join-Path $temp 'portable folder'
    & $Installer -Destination $destination
    $actual = $destination + '\RustRaptor\' + $longMember.Replace('/', '\')
    if (-not [RaptorLongPath]::Exists($actual)) { throw 'Long-path accepted proof was not installed.' }
    if (-not (Test-Path -LiteralPath (Join-Path $destination 'RustRaptor\run.cmd'))) { throw 'Platform core was not installed.' }
    # A second fresh install with a corrupted payload expectation must fail.
    $manifest.assets[0].files[0].sha256 = '0' * 64
    $manifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    $failed = $false
    try { & $Installer -Destination (Join-Path $temp 'bad hash') } catch { $failed = $true }
    if (-not $failed) { throw 'Incorrect payload SHA-256 was accepted.' }
    Write-Host 'PASS: Windows PowerShell ZIP manifest, complete payload, >260-character extraction, and bad-hash rejection.'
} finally {
    Remove-Item Function:\Invoke-WebRequest -ErrorAction SilentlyContinue
    Remove-Variable RaptorInstallerFixtureDownloads -Scope Global -ErrorAction SilentlyContinue
    # Windows built-in tar supports long-path cleanup without changing OS policy.
    if (Get-Command cmd.exe -ErrorAction SilentlyContinue) { & cmd.exe /d /c ('rmdir /s /q "' + $temp + '"') | Out-Null }
}
