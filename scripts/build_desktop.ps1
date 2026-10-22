param([switch]$InstallDependencies)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$buildId = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$buildRoot = Join-Path $projectRoot "build\desktop\$buildId"
$distributionRoot = Join-Path $projectRoot "dist\desktop\$buildId"
$reportRoot = Join-Path $projectRoot "reports\desktop\$buildId"
$oldAssets = $env:NEURALHEAT_STAGED_ASSETS
$oldPythonPath = $env:PYTHONPATH
$oldPipTemp = $env:TMPDIR
$oldLocation = Get-Location

function Invoke-Checked([string]$executable, [string[]]$arguments) {
    & $executable @arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $executable $($arguments -join ' ')" }
}

try {
    Set-Location -LiteralPath $projectRoot
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'Windows x64 is required.' }
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Missing existing .venv. Follow README developer setup first.' }
    $nodeExe = (Get-Command node.exe -ErrorAction Stop).Source
    $npmExe = (Get-Command npm.cmd -ErrorAction Stop).Source
    New-Item -ItemType Directory -Force -Path $buildRoot,$reportRoot | Out-Null
    $env:PYTHONPATH = (Join-Path $projectRoot 'src') + [IO.Path]::PathSeparator + $oldPythonPath
    $env:TMPDIR = Join-Path $buildRoot 'tmp'
    New-Item -ItemType Directory -Force -Path $env:TMPDIR | Out-Null
    Invoke-Checked $pythonExe @('-c', "import struct; assert struct.calcsize('P')==8, 'Use 64-bit Python'")
    Invoke-Checked $nodeExe @('-e', "const [a,b]=process.versions.node.split('.').map(Number);if(a<22||(a===22&&b<12))process.exit(1)")
    if ($InstallDependencies) {
        Invoke-Checked $pythonExe @('-m','pip','install','-e','.[studio,desktop,dev]')
        Invoke-Checked $npmExe @('install','--no-audit','--no-fund')
    }
    Invoke-Checked $pythonExe @('-c', "import webview, PyInstaller, PIL, numpy, torch, fastapi, uvicorn, pytest, ruff; print('Desktop dependencies ready | CUDA build:',torch.version.cuda)")
    # CPU-only torch wheels cannot produce a release with CUDA support.
    Invoke-Checked $pythonExe @('-c', "import torch; assert torch.version.cuda, 'Install a CUDA-enabled PyTorch wheel before building this release'")
    Invoke-Checked $npmExe @('run','typecheck')
    Invoke-Checked $npmExe @('run','lint')
    Invoke-Checked $npmExe @('test')
    Invoke-Checked $npmExe @('run','build')
    Invoke-Checked $pythonExe @('-m','ruff','check','src','tests','scripts')
    Invoke-Checked $pythonExe @('-m','ruff','format','--check','src','tests','scripts')
    Invoke-Checked $pythonExe @('-m','pytest','-q','--junitxml', (Join-Path $reportRoot 'pytest.xml'))
    Invoke-Checked $pythonExe @('scripts/create_desktop_icon.py')
    $assetRoot = Join-Path $buildRoot 'scientific_assets'
    Invoke-Checked $pythonExe @('scripts/stage_desktop_assets.py','--destination',$assetRoot)
    & $pythonExe -m pip freeze | Set-Content -LiteralPath (Join-Path $reportRoot 'python-environment.txt') -Encoding UTF8
    Copy-Item -LiteralPath (Join-Path $projectRoot 'package-lock.json') -Destination (Join-Path $reportRoot 'package-lock.json')
    Copy-Item -LiteralPath (Join-Path $assetRoot 'asset-manifest.json') -Destination (Join-Path $reportRoot 'asset-manifest.json')
    $env:NEURALHEAT_STAGED_ASSETS = $assetRoot
    Invoke-Checked $pythonExe @('-m','PyInstaller','--distpath',$distributionRoot,'--workpath',(Join-Path $buildRoot 'pyinstaller'),'--log-level','INFO','desktop/NeuralHeat Studio.spec')
    $executable = Join-Path $distributionRoot 'NeuralHeat Studio\NeuralHeat Studio.exe'
    if (-not (Test-Path -LiteralPath $executable)) { throw 'PyInstaller did not create the requested executable.' }
    Copy-Item -LiteralPath (Join-Path $projectRoot 'LICENSE') -Destination (Join-Path (Split-Path $executable) 'LICENSE.txt')
    Copy-Item -LiteralPath (Join-Path $projectRoot 'docs\DESKTOP.md') -Destination (Join-Path (Split-Path $executable) 'DESKTOP.md')
    Invoke-Checked $pythonExe @('scripts/write_release_notices.py','--destination',(Split-Path $executable))
    # The build is not declared successful until the actual frozen release passes.
    & (Join-Path $PSScriptRoot 'test_desktop.ps1') -Executable $executable -ReportDirectory $reportRoot
    if (-not $?) { throw 'Packaged executable verification failed.' }
    Invoke-Checked $pythonExe @('scripts/stage_desktop_assets.py','--verify-manifest',(Join-Path $assetRoot 'asset-manifest.json'))
    $release = @{ status='verified'; executable=$executable; report_directory=$reportRoot; build_id=$buildId }
    $release | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectRoot 'dist\desktop\latest.json') -Encoding UTF8
    $release | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportRoot 'release.json') -Encoding UTF8
    Write-Host "`nVerified desktop release: $executable" -ForegroundColor Green
    Write-Host 'Distribute the complete NeuralHeat Studio folder, including _internal. Double-click the EXE to launch.'
} catch {
    if (Test-Path -LiteralPath $reportRoot) {
        @{status='failed';error=$_.Exception.Message;build_id=$buildId} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportRoot 'build-failure.json') -Encoding UTF8
    }
    throw
} finally {
    $env:NEURALHEAT_STAGED_ASSETS = $oldAssets
    $env:PYTHONPATH = $oldPythonPath
    $env:TMPDIR = $oldPipTemp
    Set-Location -LiteralPath $oldLocation
}
