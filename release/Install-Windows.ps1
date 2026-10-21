param([string]$Destination = (Get-Location).Path)
$ErrorActionPreference = 'Stop'
$tag = 'v1.0.0'
$base = "https://github.com/Quintine/RustRaptor/releases/download/$tag"
if (-not [Environment]::Is64BitOperatingSystem) { throw 'RustRaptor requires 64-bit Windows.' }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
# Use wide Win32 APIs and extended paths: Windows PowerShell 5.1 Expand-Archive
# cannot reliably extract the complete accepted proof/lineage long filenames.
if (-not ('RaptorLongPath' -as [type])) {
Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.ComponentModel;
using Microsoft.Win32.SafeHandles;
public static class RaptorLongPath {
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, ExactSpelling=true, SetLastError=true)]
  static extern uint GetFileAttributesW(string name);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, ExactSpelling=true, SetLastError=true)]
  static extern bool CreateDirectoryW(string name, IntPtr security);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, ExactSpelling=true, SetLastError=true)]
  static extern SafeFileHandle CreateFileW(string name, uint access, uint share, IntPtr security, uint creation, uint flags, IntPtr template);
  static string Extended(string path) {
    if (path.StartsWith(@"\\?\")) return path;
    if (path.StartsWith(@"\\")) return @"\\?\UNC\" + path.Substring(2);
    return @"\\?\" + path;
  }
  public static bool Exists(string path) { return GetFileAttributesW(Extended(path)) != 0xffffffff; }
  public static void Directory(string path) {
    string name = Extended(path);
    uint attributes = GetFileAttributesW(name);
    if (attributes == 0xffffffff) {
      if (!CreateDirectoryW(name, IntPtr.Zero)) throw new Win32Exception(Marshal.GetLastWin32Error());
      attributes = GetFileAttributesW(name);
    }
    if ((attributes & 0x400) != 0 || (attributes & 0x10) == 0) throw new IOException("Unsafe installation directory");
  }
  public static void Extract(Stream input, string path, long expectedSize, string expectedHash) {
    using (SafeFileHandle handle = CreateFileW(Extended(path), 0x40000000, 0, IntPtr.Zero, 1, 0x80, IntPtr.Zero)) {
      if (handle.IsInvalid) throw new Win32Exception(Marshal.GetLastWin32Error());
      using (FileStream output = new FileStream(handle, FileAccess.Write))
      using (var sha = System.Security.Cryptography.SHA256.Create()) {
        byte[] buffer = new byte[131072]; long count = 0; int read;
        while ((read = input.Read(buffer, 0, buffer.Length)) != 0) {
          count += read; if (count > expectedSize) throw new IOException("Payload exceeds planned size");
          sha.TransformBlock(buffer, 0, read, buffer, 0); output.Write(buffer, 0, read);
        }
        sha.TransformFinalBlock(new byte[0], 0, 0);
        string hash = BitConverter.ToString(sha.Hash).Replace("-", "").ToLowerInvariant();
        if (count != expectedSize || hash != expectedHash) throw new IOException("Installed payload size or SHA-256 mismatch");
      }
    }
  }
}
'@
}
function Assert-Member([string]$Name) {
    if (-not $Name.StartsWith('RustRaptor/') -or $Name.Contains('\')) { throw 'Unsafe ZIP member path.' }
    foreach ($part in $Name.Split('/')) {
        if ($part -eq '' -or $part -eq '.' -or $part -eq '..' -or $part -match '[<>:"|?*\x00-\x1f]' -or
            $part.EndsWith('.') -or $part.EndsWith(' ') -or $part -match '^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)') {
            throw 'Unsafe or nonportable ZIP member path.'
        }
    }
}
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$Destination = (Resolve-Path -LiteralPath $Destination).Path
[RaptorLongPath]::Directory($Destination)
$installation = $Destination.TrimEnd('\') + '\RustRaptor'
if ([RaptorLongPath]::Exists($installation)) { throw 'Use a directory without an existing RustRaptor folder.' }
$cache = Join-Path ([IO.Path]::GetTempPath()) ('RustRaptor-download-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $cache | Out-Null
try {
    $manifestPath = Join-Path $cache 'release-manifest.json'
    Invoke-WebRequest -UseBasicParsing -Uri "$base/release-manifest.json" -OutFile $manifestPath
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.format_version -ne 1 -or $manifest.tag -cne $tag) { throw 'Wrong release manifest version or tag.' }
    $assets = @($manifest.assets | Where-Object { $_.kind -in @('shared-data', 'windows') })
    $data = @($assets | Where-Object { $_.kind -eq 'shared-data' })
    $names = @{}
    $paths = @{}
    $platformCount = 0
    $required = @{}
    for ($i = 1; $i -le $data.Count; $i++) { $required.Add(('RustRaptor-data-{0:D2}-of-{1:D2}.zip' -f $i, $data.Count), $true) }
    foreach ($asset in $assets) {
        if ($names.ContainsKey($asset.name)) { throw 'Duplicate release asset name.' }
        $names.Add($asset.name, $true)
        if ($asset.kind -eq 'windows') {
            if ($asset.name -cne 'RustRaptor-windows-x86_64.zip') { throw 'Wrong platform archive name.' }
            $platformCount++
        } elseif (-not $required.ContainsKey($asset.name)) { throw 'Incomplete data-volume sequence.' }
        if ($asset.sha256 -cnotmatch '^[0-9a-f]{64}$' -or $asset.bytes -le 0 -or $asset.bytes -ge 2147483648) { throw 'Invalid asset size or SHA-256.' }
        foreach ($row in $asset.files) {
            Assert-Member ('RustRaptor/' + $row.name)
            if ($paths.ContainsKey($row.name)) { throw 'Duplicate installation path across archives.' }
            $paths.Add($row.name, $true)
            if ($row.bytes -lt 0 -or $row.sha256 -cnotmatch '^[0-9a-f]{64}$') { throw 'Invalid payload size or SHA-256.' }
        }
    }
    if ($platformCount -ne 1 -or $data.Count -eq 0 -or $assets.Count -ne ($data.Count + 1)) { throw 'Incomplete release asset manifest.' }
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    foreach ($asset in $assets) {
        $name = $asset.name
        Write-Host "Downloading $name"
        $archivePath = Join-Path $cache $name
        Invoke-WebRequest -UseBasicParsing -Uri "$base/$name" -OutFile $archivePath
        if ((Get-Item -LiteralPath $archivePath).Length -ne $asset.bytes -or
            (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $asset.sha256) {
            throw "Downloaded archive size or SHA-256 mismatch: $name"
        }
        $expected = @{}
        foreach ($row in $asset.files) { $expected.Add(('RustRaptor/' + $row.name), $row) }
        $archive = [IO.Compression.ZipFile]::OpenRead($archivePath)
        try {
            if ($archive.Entries.Count -ne $expected.Count) { throw 'ZIP membership differs from frozen manifest.' }
            $seen = @{}
            foreach ($entry in $archive.Entries) {
                Assert-Member $entry.FullName
                if (-not $expected.ContainsKey($entry.FullName) -or $seen.ContainsKey($entry.FullName)) { throw 'Unexpected or duplicate ZIP member.' }
                $seen.Add($entry.FullName, $true)
                $row = $expected[$entry.FullName]
                $mode = ($entry.ExternalAttributes -shr 16) -band 0xF000
                if ($mode -ne 0 -and $mode -ne 0x8000) { throw 'ZIP member is not an ordinary file.' }
                if ($entry.Length -ne $row.bytes) { throw 'ZIP member size differs from frozen manifest.' }
            }
            foreach ($entry in $archive.Entries) {
                $parts = $entry.FullName.Split('/')
                $parent = $Destination.TrimEnd('\')
                for ($i = 0; $i -lt ($parts.Length - 1); $i++) {
                    $parent += '\' + $parts[$i]
                    [RaptorLongPath]::Directory($parent)
                }
                $target = $parent + '\' + $parts[$parts.Length - 1]
                $source = $entry.Open()
                try { [RaptorLongPath]::Extract($source, $target, $expected[$entry.FullName].bytes, $expected[$entry.FullName].sha256) }
                finally { $source.Dispose() }
            }
        } finally { $archive.Dispose() }
        Remove-Item -LiteralPath $archivePath
    }
    Write-Host ('Installed. Start ' + $installation + '\run.cmd')
} catch {
    Write-Warning 'Installation did not complete. Any partial RustRaptor folder has been preserved; move or remove it before retrying.'
    throw
} finally {
    Remove-Item -LiteralPath $cache -Recurse -Force
}
