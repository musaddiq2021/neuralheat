param(
    [string]$Bundle,
    [ValidateSet('TarXz','SevenZip')][string]$Format = 'TarXz',
    [string]$SevenZip,
    [ValidateRange(1,8)][int]$Threads = 2,
    [ValidateRange(1,9)][int]$CompressionLevel = 8
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$runId = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$output = Join-Path $projectRoot "dist\distribution\$runId"
$reports = Join-Path $projectRoot "reports\distribution\$runId"
$tarExe = Join-Path $env:SystemRoot 'System32\tar.exe'
$previousLocation = Get-Location

function Invoke-Checked([string]$executable, [string[]]$arguments) {
    & $executable @arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $executable" }
}

try {
    Set-Location -LiteralPath $projectRoot
    if (-not $Bundle) { $Bundle = Split-Path ((Get-Content dist/desktop/latest.json -Raw | ConvertFrom-Json).executable) }
    $bundlePath = (Resolve-Path -LiteralPath $Bundle).Path
    if (-not (Test-Path -LiteralPath (Join-Path $bundlePath 'NeuralHeat Studio.exe'))) { throw 'Select an existing working onedir bundle.' }
    New-Item -ItemType Directory -Path $output,$reports | Out-Null
    Invoke-Checked $pythonExe @('scripts/audit_desktop_bundle.py','--bundle',$bundlePath,'--output',$reports)
    $manifest = Join-Path $reports 'bundle-audit.json'
    $baseName = 'NeuralHeat-Studio-Windows-CUDA'
    $bundleParent = Split-Path $bundlePath
    $bundleName = Split-Path $bundlePath -Leaf
    $started = Get-Date
    if ($Format -eq 'SevenZip') {
        $archive = Join-Path $output "$baseName.7z"
        if (-not $SevenZip) {
            $command = Get-Command 7z.exe -ErrorAction SilentlyContinue
            if ($command) { $SevenZip = $command.Source }
        }
        if ($SevenZip) { $SevenZip = (Resolve-Path -LiteralPath $SevenZip).Path }
        Set-Location -LiteralPath $bundleParent
        if ($SevenZip) {
            Invoke-Checked $SevenZip @('a','-t7z','-m0=LZMA2','-mx=9','-md=64m','-ms=on',"-mmt=$Threads",'-bsp0',$archive,$bundleName)
        } else {
            # Built-in Windows libarchive supports the 7z container. Its LZMA2
            # writer is single-threaded; threads options apply to other codecs.
            Invoke-Checked $tarExe @('-c','--format=7zip','--options','compression=lzma2,compression-level=9','-f',$archive,$bundleName)
        }
    } else {
        $archive = Join-Path $output "$baseName.tar.xz"
        Invoke-Checked $tarExe @('-cJ','--options',"xz:threads=$Threads,xz:compression-level=$CompressionLevel",'-f',$archive,'-C',$bundleParent,$bundleName)
    }
    $compressionSeconds = ((Get-Date) - $started).TotalSeconds
    Set-Location -LiteralPath $projectRoot
    $effectiveLevel = if ($Format -eq 'SevenZip') { 9 } else { $CompressionLevel }
    @{format=$Format;compression_seconds=$compressionSeconds;threads=$Threads;compression_level=$effectiveLevel;archive=$archive} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reports 'compression.json') -Encoding UTF8
    $extraction = Join-Path $output 'extracted'
    New-Item -ItemType Directory -Path $extraction | Out-Null
    Invoke-Checked $tarExe @('-xf',$archive,'-C',$extraction)
    $extractedBundle = Join-Path $extraction $bundleName
    Invoke-Checked $pythonExe @('scripts/verify_distribution.py','--integrity-only','--audit',$manifest,'--extracted',$extractedBundle)
    $candidate = @{archive=$archive;extracted_bundle=$extractedBundle;audit_manifest=$manifest;report_directory=$reports}
    $candidatePath = Join-Path $reports 'candidate.json'
    $candidate | ConvertTo-Json | Set-Content -LiteralPath $candidatePath -Encoding UTF8
    $candidate | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectRoot 'reports\distribution\candidate.json') -Encoding UTF8
    & (Join-Path $PSScriptRoot 'test_distribution.ps1') -CandidateFile $candidatePath
    Write-Host "Verified portable archive below 1.9 GiB: $archive" -ForegroundColor Green
    Write-Host "Reports: $reports"
} finally {
    Set-Location -LiteralPath $previousLocation
}
