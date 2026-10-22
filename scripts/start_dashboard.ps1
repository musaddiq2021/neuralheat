param([switch]$NoBrowser, [switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontendRoot = Join-Path $projectRoot 'frontend'
$viteScript = $null
$backendProcess = $null
$frontendProcess = $null
$previousPythonPath = $env:PYTHONPATH

Write-Host "`nNEURALHEAT STUDIO | local scientific workstation" -ForegroundColor Cyan
Write-Host "Workspace: $projectRoot"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'Missing .venv Python environment. Follow the README Python setup before launching Studio.'
}
$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $nodeCommand) { throw 'Node.js 22.12+ (or Node 24 LTS) must be installed and available on PATH.' }
$nodeExe = $nodeCommand.Source
& $nodeExe -e "const [a,b]=process.versions.node.split('.').map(Number);if(a<22||(a===22&&b<12))process.exit(1)"
if ($LASTEXITCODE -ne 0) { throw 'Studio requires Node.js 22.12+ or Node 24 LTS.' }
& $pythonExe -c "import numpy, torch, fastapi, uvicorn; print('Python dependencies ready | PyTorch',torch.__version__,'| CUDA',torch.cuda.is_available())"
if ($LASTEXITCODE -ne 0) { throw 'Backend dependencies are missing. Run: .\.venv\Scripts\python.exe -m pip install -e ".[studio,dev]"' }
$resolveModules = "try { const opts={paths:[process.argv[1]]}; process.stdout.write(JSON.stringify({vite:require.resolve('vite/package.json',opts),reactFlow:require.resolve('@xyflow/react',opts)})); } catch { process.stdout.write('{}'); process.exitCode=1; }"
$moduleResolution = & $nodeExe -e $resolveModules -- $frontendRoot
if ($LASTEXITCODE -ne 0) {
    throw 'Frontend dependencies are missing. Run: npm.cmd --prefix frontend install'
}
$resolvedModules = $moduleResolution | ConvertFrom-Json
$viteScript = Join-Path (Split-Path -Parent $resolvedModules.vite) 'bin\vite.js'
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'models\best.pt'))) {
    Write-Warning 'No models/best.pt checkpoint. Solver and report views work; CNN inspection will show unavailable.'
}
if ($CheckOnly) { Write-Host 'All dashboard dependency checks passed.' -ForegroundColor Green; return }

$runtimeDir = Join-Path $projectRoot '.cache\studio'
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

function Test-StudioBackend {
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        return $health.application -eq 'NEURALHEAT Studio'
    } catch { return $false }
}
function Test-StudioFrontend {
    try {
        $page = Invoke-WebRequest 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 2
        return $page.Content -match '<title>NEURALHEAT Studio</title>'
    } catch { return $false }
}
function Test-ListeningPort([int]$port) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return [bool]$listener
}

try {
    $env:PYTHONPATH = (Join-Path $projectRoot 'src') + [IO.Path]::PathSeparator + $previousPythonPath
    if (-not (Test-StudioBackend)) {
        if (Test-ListeningPort 8000) { throw 'Port 8000 is used by another service. Stop it or launch Studio after freeing the port.' }
        Write-Host 'Starting FastAPI on http://127.0.0.1:8000 (one worker, one loaded checkpoint)...'
        $backendProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','neuralheat.studio.app:app','--host','127.0.0.1','--port','8000','--workers','1') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir 'backend.log') -RedirectStandardError (Join-Path $runtimeDir 'backend.error.log')
    } else { Write-Host 'Reusing the existing NEURALHEAT Studio backend.' }
    if (-not (Test-StudioFrontend)) {
        if (Test-ListeningPort 5173) { throw 'Port 5173 is used by another service. Free the port before starting Studio.' }
        Write-Host 'Starting Vite on http://127.0.0.1:5173...'
        $frontendProcess = Start-Process -FilePath $nodeExe -ArgumentList @(('"' + $viteScript + '"'),'--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir 'frontend.log') -RedirectStandardError (Join-Path $runtimeDir 'frontend.error.log')
    } else { Write-Host 'Reusing the existing NEURALHEAT Studio frontend.' }
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($backendProcess -and $backendProcess.HasExited) { throw "Backend exited. See $runtimeDir\backend.error.log" }
        if ($frontendProcess -and $frontendProcess.HasExited) { throw "Frontend exited. See $runtimeDir\frontend.error.log" }
        if ((Test-StudioBackend) -and (Test-StudioFrontend)) { $ready = $true; break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "Studio did not become ready. Inspect the logs in $runtimeDir" }
    Write-Host "`nStudio ready: http://127.0.0.1:5173" -ForegroundColor Green
    Write-Host 'API documentation: http://127.0.0.1:8000/docs'
    Write-Host 'Press Ctrl+C to stop processes started by this launcher. Existing services are left running.'
    if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:5173' }
    while ($true) {
        if (($backendProcess -and $backendProcess.HasExited) -or ($frontendProcess -and $frontendProcess.HasExited)) { throw "A dashboard process exited. Inspect $runtimeDir" }
        Start-Sleep -Seconds 1
    }
} finally {
    if ($frontendProcess -and -not $frontendProcess.HasExited) { Stop-Process -Id $frontendProcess.Id -ErrorAction SilentlyContinue }
    if ($backendProcess -and -not $backendProcess.HasExited) { Stop-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue }
    $env:PYTHONPATH = $previousPythonPath
}
