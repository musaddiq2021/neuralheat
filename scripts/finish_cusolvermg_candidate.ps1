param(
    [string]$Executable,
    [switch]$AllUsers,
    [string]$RuntimeVerificationDirectory,
    [switch]$BuildOnly
)

# Run outside the restricted executor. Nothing is uploaded or promoted.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not $Executable) { throw 'Pass the new experimental executable, not the original verified release.' }
$Executable = (Resolve-Path -LiteralPath $Executable).Path
$experimentalRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'dist\experiments')) + '\'
if (-not $Executable.StartsWith($experimentalRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Only an isolated experimental payload is accepted.' }
$bundle = Split-Path -Parent $Executable
if (Test-Path -LiteralPath (Join-Path $bundle '_internal\torch\lib\cusolverMg64_11.dll')) { throw 'The candidate still includes cuSOLVERMg.' }
$runId = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$runtime = if ($RuntimeVerificationDirectory) { (Resolve-Path -LiteralPath $RuntimeVerificationDirectory).Path } else { Join-Path $projectRoot "reports\redistribution\finalize-$runId\runtime" }
$savedLocation = Get-Location
try {
    Set-Location -LiteralPath $projectRoot
    if ($RuntimeVerificationDirectory) {
        $verification = Get-Content -LiteralPath (Join-Path $runtime 'verified-candidate.json') -Raw | ConvertFrom-Json
        $runtimeTests = Get-Content -LiteralPath (Join-Path $runtime 'runtime-tests.json') -Raw | ConvertFrom-Json
        $exeHash = (Get-FileHash -LiteralPath $Executable -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($verification.executable -ne $Executable -or $verification.executable_sha256 -ne $exeHash -or $runtimeTests.status -ne 'passed' -or $runtimeTests.tests.Count -ne 3 -or @($runtimeTests.tests | Where-Object { -not $_.passed }).Count -ne 0) {
            throw 'Saved runtime verification does not match this candidate or contains failed checks.'
        }
    } else {
        & $pythonExe scripts/test_redistribution_candidate.py --executable $Executable --output $runtime
        if ($LASTEXITCODE -ne 0) { throw 'All frozen CPU/CUDA/worker/UI tests must pass before installer compilation.' }
    }
    $msvcReview = Get-Content -LiteralPath (Join-Path $projectRoot 'docs\licenses\msvc-provenance.json') -Raw | ConvertFrom-Json
    if (-not $msvcReview.msvc_redistribution_fully_resolved) { throw 'Complete the actual MSVC licence/provenance review before compiling the distribution installer.' }
    & $pythonExe scripts/prepare_release_notices.py
    if ($LASTEXITCODE -ne 0) { throw 'Complete release notices could not be prepared.' }
    # Add the complete accompanying notices and covered source inside this
    # candidate only. Scientific asset hashes and the original release stay intact.
    $notices = Join-Path $projectRoot 'dist\release-support\NeuralHeat-Studio-Third-Party-Notices.txt'
    $covered = Join-Path $projectRoot 'dist\release-support\NeuralHeat-Studio-Certifi-2026.4.22-Source.zip'
    Copy-Item -LiteralPath $notices -Destination (Join-Path $bundle 'THIRD_PARTY_NOTICES.txt') -Force
    $licenseDirectory = Join-Path $bundle 'third-party-licenses\certifi'
    New-Item -ItemType Directory -Path $licenseDirectory -Force | Out-Null
    Copy-Item -LiteralPath $covered -Destination (Join-Path $licenseDirectory 'corresponding-source.zip') -Force
    Copy-Item -LiteralPath (Join-Path $projectRoot 'docs\licenses\BINARY_DISTRIBUTION_TERMS.txt') -Destination (Join-Path $bundle 'BINARY_DISTRIBUTION_TERMS.txt') -Force
    $agreement = (Get-Content -LiteralPath (Join-Path $projectRoot 'LICENSE') -Raw) + "`r`n`r`n" + (Get-Content -LiteralPath (Join-Path $projectRoot 'docs\licenses\BINARY_DISTRIBUTION_TERMS.txt') -Raw)
    [IO.File]::WriteAllText((Join-Path $bundle 'INSTALLATION-LICENCE.txt'),$agreement,(New-Object Text.UTF8Encoding($false)))
    # Inno compiles a new timestamped installer from the tested payload. It
    # never overwrites the original setup or dist/desktop/latest.json.
    & (Join-Path $PSScriptRoot 'build_installer.ps1') -SourceExecutable $Executable -SourceVerificationDirectory $runtime -BuildOnly
    if (-not $?) { throw 'Candidate installer compilation failed.' }
    $candidate = Join-Path $projectRoot 'reports\installer\candidate.json'
    if (-not $BuildOnly) {
        & (Join-Path $PSScriptRoot 'test_installer.ps1') -CandidateFile $candidate -AllUsers:$AllUsers -TestDesktopShortcut -TestUninstall
        if (-not $?) { throw 'Installed executable verification did not pass.' }
        Write-Host 'The Mg-free installer passed installation tests. No release has been published.'
    } else {
        Write-Host "Installer built; run scripts/test_installer.ps1 -CandidateFile `"$candidate`" -TestDesktopShortcut -TestUninstall from normal Windows PowerShell."
    }
} finally { Set-Location -LiteralPath $savedLocation }
