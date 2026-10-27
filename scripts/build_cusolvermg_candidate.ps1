param([switch]$BuildOnly, [string]$ResumeBuildId)

# Build into a unique experimental directory; never promote a release pointer.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$latest = Get-Content -LiteralPath (Join-Path $projectRoot 'dist\desktop\latest.json') -Raw | ConvertFrom-Json
if ($latest.status -ne 'verified') { throw 'A verified original payload is required.' }
$buildId = if ($ResumeBuildId) { $ResumeBuildId } else { 'no-cusolvermg-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') }
if ($buildId -notmatch '^no-cusolvermg-\d{8}-\d{6}-\d{3}$') { throw 'Invalid experimental build ID.' }
$workRoot = Join-Path $projectRoot "build\experiments\$buildId"
$distRoot = Join-Path $projectRoot "dist\experiments\$buildId"
$reportRoot = Join-Path $projectRoot "reports\redistribution\$buildId"
if (-not $ResumeBuildId) { New-Item -ItemType Directory -Path $workRoot,$reportRoot | Out-Null }
$original = Split-Path -Parent $latest.executable
$assets = Join-Path $original '_internal\scientific_assets'
$savedAssets = $env:NEURALHEAT_STAGED_ASSETS
$savedLocation = Get-Location
try {
    Set-Location -LiteralPath $projectRoot
    $env:NEURALHEAT_STAGED_ASSETS = $assets
    if (-not $ResumeBuildId) {
        # Python owns the process handle and captures the real exit status;
        # Windows PowerShell can expose a null ExitCode after WaitForExit.
        $freezeCode = @'
import pathlib, subprocess, sys
dist, work, reports = sys.argv[1:]
with (pathlib.Path(reports) / 'freeze.log').open('w', encoding='utf-8') as log:
    result = subprocess.run([sys.executable, '-m', 'PyInstaller', '--distpath', dist, '--workpath', work, '--log-level', 'INFO', 'desktop/experiments/no-cusolvermg.spec'], stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
raise SystemExit(result.returncode)
'@
        & $pythonExe -c $freezeCode $distRoot $workRoot $reportRoot
        if ($LASTEXITCODE -ne 0) { throw "Experimental freeze failed. See $reportRoot\freeze.log. The original remains unchanged." }
    } else {
        $log = Get-Content -LiteralPath (Join-Path $reportRoot 'freeze.log') -Raw
        if ($log -notmatch 'Building COLLECT.*completed successfully' -or $log -notmatch 'Build complete!') { throw 'The selected build did not complete its collection.' }
    }
    $bundle = Join-Path $distRoot 'NeuralHeat Studio'
    if (-not (Test-Path -LiteralPath (Join-Path $bundle 'NeuralHeat Studio.exe'))) { throw 'The frozen candidate is missing.' }
    if (Test-Path -LiteralPath (Join-Path $bundle '_internal\torch\lib\cusolverMg64_11.dll')) { throw 'The experimental exclusion was not applied.' }
    foreach ($name in @('LICENSE.txt','DESKTOP.md','THIRD_PARTY_NOTICES.txt','third-party-licenses')) {
        $item = Join-Path $original $name
        if ((Test-Path -LiteralPath $item) -and -not (Test-Path -LiteralPath (Join-Path $bundle $name))) { Copy-Item -LiteralPath $item -Destination $bundle -Recurse }
    }
    $candidate = Join-Path $bundle 'NeuralHeat Studio.exe'
    @{status='experimental_not_release'; executable=$candidate; original=$latest.executable; report_directory=$reportRoot; promoted=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportRoot 'candidate.json') -Encoding UTF8
    Write-Host "Experimental executable: $candidate"
    if (-not $BuildOnly) {
        & $pythonExe scripts/test_redistribution_candidate.py --executable $candidate --output (Join-Path $reportRoot 'runtime')
        if ($LASTEXITCODE -ne 0) { throw 'Candidate tests did not all pass; do not promote or replace the verified installer.' }
    }
} finally {
    $env:NEURALHEAT_STAGED_ASSETS = $savedAssets
    Set-Location -LiteralPath $savedLocation
}
