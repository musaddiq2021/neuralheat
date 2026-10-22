param([string]$Executable, [string]$ReportDirectory)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Executable) {
    $latest = Join-Path $projectRoot 'dist\desktop\latest.json'
    if (-not (Test-Path -LiteralPath $latest)) { throw 'No verified desktop release. Run scripts/build_desktop.ps1 first, or pass -Executable.' }
    $Executable = (Get-Content -LiteralPath $latest -Raw | ConvertFrom-Json).executable
}
$exePath = (Resolve-Path -LiteralPath $Executable).Path
if (-not $ReportDirectory) { $ReportDirectory = Join-Path $projectRoot ('reports\desktop\retest-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')) }
New-Item -ItemType Directory -Force -Path $ReportDirectory | Out-Null
$reportRoot = (Resolve-Path -LiteralPath $ReportDirectory).Path
$testId = [Guid]::NewGuid().ToString('N')
$userRoot = Join-Path $projectRoot ".cache\desktop-release-tests\$testId"
New-Item -ItemType Directory -Force -Path $userRoot | Out-Null
$oldLocation = Get-Location
$oldPath = $env:PATH
$oldPythonPath = $env:PYTHONPATH
$oldPythonHome = $env:PYTHONHOME
$oldProxy = $env:HTTP_PROXY
$oldHttpsProxy = $env:HTTPS_PROXY

function Invoke-ReleaseTest([string]$name, [string[]]$extra) {
    $report = Join-Path $reportRoot "$name.json"
    # Native argument passing requires explicit quoting for spaces in paths.
    $arguments = @('--self-test','--user-data-dir',('"'+$userRoot+'"'),'--test-report',('"'+$report+'"')) + $extra
    $process = Start-Process -FilePath $exePath -ArgumentList $arguments -WindowStyle Hidden -PassThru
    try {
        if (-not $process.WaitForExit(600000)) {
            $process.Kill()
            throw "Packaged $name verification timed out. Logs: $userRoot\logs"
        }
        if ($process.ExitCode -ne 0) { throw "Packaged $name verification failed ($($process.ExitCode)). See $report and $userRoot\logs" }
        if (-not (Test-Path -LiteralPath $report)) { throw "Executable did not produce its $name report." }
        $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
        if (-not $result.frozen -or $result.status -ne 'passed' -or -not $result.backend_port_closed) {
            throw "Frozen release checks did not pass: $report"
        }
        Write-Host "$name passed | device=$($result.device) | checkpoint=$($result.checkpoint_sha256)" -ForegroundColor Green
    } finally { $process.Dispose() }
}

try {
    # Remove developer runtimes and block HTTP(S) proxies: the release must be
    # self-contained. This is not a firewall-level network isolation test.
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $env:PYTHONPATH = $null
    $env:PYTHONHOME = $null
    $env:HTTP_PROXY = 'http://127.0.0.1:9'
    $env:HTTPS_PROXY = 'http://127.0.0.1:9'
    Set-Location -LiteralPath $userRoot
    Invoke-ReleaseTest 'packaged-cpu' @('--device','cpu')
    Invoke-ReleaseTest 'packaged-webview-cuda-worker' @('--device','auto','--ui-test','--verify-worker')
    Write-Host "Release reports: $reportRoot"
} finally {
    $env:PATH = $oldPath
    $env:PYTHONPATH = $oldPythonPath
    $env:PYTHONHOME = $oldPythonHome
    $env:HTTP_PROXY = $oldProxy
    $env:HTTPS_PROXY = $oldHttpsProxy
    Set-Location -LiteralPath $oldLocation
}
