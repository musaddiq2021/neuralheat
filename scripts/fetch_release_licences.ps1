param([string]$Destination)

# Download evidence only. Never installs a runtime, accepts terms or replaces DLLs.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Destination) { $Destination = Join-Path $projectRoot '.cache\licensing' }
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$downloads = @(
    @{
        name='Visual_Studio_2026-License-Community_ENU.docx'
        url='https://visualstudio.microsoft.com/wp-content/uploads/2025/10/Visual_Studio_2026-License-Community_ENU.docx'
        sha256=$null
    },
    @{
        name='VC_redist.x64-14.40.33810.exe'
        url='https://download.visualstudio.microsoft.com/download/pr/1754ea58-11a6-44ab-a262-696e194ce543/3642E3F95D50CC193E4B5A0B0FFBF7FE2C08801517758B4C8AEB7105A091208A/VC_redist.x64.exe'
        # Microsoft's winget-pkgs manifest, Microsoft.VCRedist.2015+.x64 14.40.33810.0.
        sha256='3642e3f95d50cc193e4b5a0b0ffbf7fe2c08801517758b4c8aeb7105a091208a'
    }
)
$records = @()
foreach ($item in $downloads) {
    $target = Join-Path $Destination $item.name
    if (-not (Test-Path -LiteralPath $target)) {
        $temporary = $target + '.download'
        Invoke-WebRequest -UseBasicParsing -Uri $item.url -OutFile $temporary -TimeoutSec 120
        $downloadedHash = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($item.sha256 -and $downloadedHash -ne $item.sha256) { throw 'Downloaded runtime does not match the official manifest SHA256.' }
        Move-Item -LiteralPath $temporary -Destination $target
    }
    $hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($item.sha256 -and $hash -ne $item.sha256) { throw "Existing evidence has an unexpected hash: $target" }
    $signature = $null
    if ($target.EndsWith('.exe')) {
        $signed = Get-AuthenticodeSignature -LiteralPath $target
        if ($signed.Status -ne 'Valid' -or $signed.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
            throw 'The archived runtime must have a valid Microsoft signature.'
        }
        $signature = @{status=$signed.Status.ToString();signer=$signed.SignerCertificate.Subject}
    } else {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $archive = [IO.Compression.ZipFile]::OpenRead($target)
        try { if (-not $archive.GetEntry('word/document.xml')) { throw 'The licence download is not a valid Word document.' } }
        finally { $archive.Dispose() }
    }
    $records += @{file=$item.name;source_url=$item.url;sha256=$hash;bytes=(Get-Item -LiteralPath $target).Length;signature=$signature}
    Write-Host "Verified evidence: $target"
}
@{retrieved_at=[DateTime]::UtcNow.ToString('o');files=$records;software_installed=$false;licence_accepted_by_script=$false} |
    ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $Destination 'official-downloads.json') -Encoding UTF8
