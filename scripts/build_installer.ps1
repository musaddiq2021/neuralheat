param(
    [string]$Compiler,
    [string]$SourceExecutable,
    [string]$SourceVerificationDirectory,
    [string]$WebView2Installer,
    [switch]$BuildOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$buildId = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$reportRoot = Join-Path $projectRoot "reports\installer\$buildId"
$releaseRoot = Join-Path $projectRoot "dist\installer\$buildId"
$previousLocation = Get-Location

function Invoke-Checked([string]$program, [string[]]$arguments) {
    & $program @arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $program" }
}

try {
    Set-Location -LiteralPath $projectRoot
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'The developer .venv is missing.' }
    if (-not $Compiler) {
        $found = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        if ($found) { $Compiler = $found.Source }
        $compilerCandidates = @(
            "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe",
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 7\ISCC.exe",
            "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
        )
        foreach ($path in $compilerCandidates) {
            if (-not $Compiler -and (Test-Path -LiteralPath $path)) { $Compiler = $path }
        }
    }
    if (-not $Compiler) { throw 'ISCC.exe not found. Install Inno Setup 6.3+ or 7, or pass -Compiler.' }
    $Compiler = (Resolve-Path -LiteralPath $Compiler).Path
    if (-not $SourceExecutable) {
        $latest = Get-Content -LiteralPath (Join-Path $projectRoot 'dist\desktop\latest.json') -Raw | ConvertFrom-Json
        if ($latest.status -ne 'verified') { throw 'The existing desktop release is not marked verified.' }
        $SourceExecutable = $latest.executable
        $SourceVerificationDirectory = $latest.report_directory
    }
    if (-not $SourceVerificationDirectory) { throw 'Pass -SourceVerificationDirectory with a custom -SourceExecutable.' }
    $SourceExecutable = (Resolve-Path -LiteralPath $SourceExecutable).Path
    $sourceRoot = Split-Path -Parent $SourceExecutable
    foreach ($name in @('packaged-cpu','packaged-webview-cuda-worker')) {
        $check = Get-Content -LiteralPath (Join-Path $SourceVerificationDirectory "$name.json") -Raw | ConvertFrom-Json
        if ($check.status -ne 'passed' -or -not $check.frozen -or -not $check.backend_port_closed) {
            throw "The source release has no passing frozen $name verification."
        }
    }
    $cudaSource = $check.device -eq 'cuda'
    $runtimeSignature = $null
    if ($WebView2Installer) {
        $WebView2Installer = (Resolve-Path -LiteralPath $WebView2Installer).Path
        $runtimeSignature = Get-AuthenticodeSignature -LiteralPath $WebView2Installer
        if ($runtimeSignature.Status -ne 'Valid' -or $runtimeSignature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
            throw 'The supplied WebView2 installer must have a valid Microsoft Authenticode signature.'
        }
        if ((Get-Item -LiteralPath $WebView2Installer).Length -lt 50MB) {
            throw 'Supply the full x64 Evergreen Standalone Installer, not the online bootstrapper.'
        }
    }
    New-Item -ItemType Directory -Path $reportRoot,$releaseRoot | Out-Null
    $artwork = Join-Path $reportRoot 'artwork'
    $assetArguments = @('scripts/create_installer_assets.py','--destination',$artwork,'--icon',(Join-Path $sourceRoot '_internal\scientific_assets\desktop\neuralheat.ico'))
    if ($WebView2Installer) { $assetArguments += '--includes-webview' }
    Invoke-Checked $pythonExe $assetArguments
    Invoke-Checked $pythonExe @('scripts/installer_release.py','prepare','--source',$sourceRoot,'--output',$reportRoot)
    $manifest = Join-Path $reportRoot 'bundle-audit.json'
    $version = (Get-Item -LiteralPath $SourceExecutable).VersionInfo.ProductVersion
    if ($version -notmatch '^\d+\.\d+\.\d+(\.\d+)?$') { throw 'The source EXE has no usable product version.' }
    $candidate = @{
        build_id=$buildId; installer=(Join-Path $releaseRoot 'NeuralHeat-Studio-Setup.exe')
        source_executable=$SourceExecutable; source_manifest=$manifest; source_cuda_verified=$cudaSource
        source_verification_directory=$SourceVerificationDirectory
        compiler=$Compiler; compiler_sha256=(Get-FileHash -LiteralPath $Compiler -Algorithm SHA256).Hash.ToLowerInvariant()
        webview2_installer=$WebView2Installer; report_directory=$reportRoot
        installer_script_sha256=(Get-FileHash -LiteralPath 'desktop\installer\NeuralHeatStudio.iss' -Algorithm SHA256).Hash.ToLowerInvariant()
        status='prepared'; version=$version
    }
    $candidateFile = Join-Path $reportRoot 'candidate.json'
    $candidate | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $candidateFile -Encoding UTF8
    $candidate | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $projectRoot 'reports\installer\candidate.json') -Encoding UTF8
    $compileArguments = @('/Qp',('/DSourceDir='+$sourceRoot),('/DReleaseDir='+$releaseRoot),('/DArtworkDir='+$artwork),('/DAppVersion='+$version))
    if ($WebView2Installer) { $compileArguments += '/DWebView2Installer='+$WebView2Installer }
    $compileArguments += (Join-Path $projectRoot 'desktop\installer\NeuralHeatStudio.iss')
    Write-Host "Compiler: $Compiler"
    Write-Host "Packaging existing release: $sourceRoot"
    Write-Host 'Lossless LZMA2 compression may take 20-40 minutes. All application files are included.'
    $timer = [Diagnostics.Stopwatch]::StartNew()
    & $Compiler @compileArguments 2>&1 | Tee-Object -FilePath (Join-Path $reportRoot 'compile.log')
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed ($LASTEXITCODE). See $reportRoot\compile.log" }
    $timer.Stop()
    if (-not (Test-Path -LiteralPath $candidate.installer)) { throw 'Compiler did not produce the installer.' }
    Invoke-Checked $pythonExe @('scripts/installer_release.py','verify','--installed',$sourceRoot,'--manifest',$manifest,'--output',(Join-Path $reportRoot 'source-preservation.json'))
    $candidate.status = 'built_not_install_verified'
    $candidate.compile_seconds = $timer.Elapsed.TotalSeconds
    $candidate.installer_bytes = (Get-Item -LiteralPath $candidate.installer).Length
    $candidate.installer_sha256 = (Get-FileHash -LiteralPath $candidate.installer -Algorithm SHA256).Hash.ToLowerInvariant()
    $candidate | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $candidateFile -Encoding UTF8
    $candidate | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $projectRoot 'reports\installer\candidate.json') -Encoding UTF8
    ($candidate.installer_sha256+'  NeuralHeat-Studio-Setup.exe') | Set-Content -LiteralPath ($candidate.installer+'.sha256') -Encoding ASCII
    Write-Host ("Installer built: {0}`nSize: {1:N6} GB / {2:N6} GiB ({3:N0} bytes)" -f $candidate.installer,($candidate.installer_bytes/1e9),($candidate.installer_bytes/1GB),$candidate.installer_bytes) -ForegroundColor Green
    if (-not $BuildOnly) {
        & (Join-Path $PSScriptRoot 'test_installer.ps1') -CandidateFile $candidateFile
    } else {
        Write-Host "Installation is not verified yet. Resume with scripts/test_installer.ps1 -CandidateFile `"$candidateFile`""
    }
} catch {
    if (Test-Path -LiteralPath $reportRoot) {
        @{status='failed';error=$_.Exception.Message;build_id=$buildId} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportRoot 'build-failure.json') -Encoding UTF8
    }
    throw
} finally { Set-Location -LiteralPath $previousLocation }
