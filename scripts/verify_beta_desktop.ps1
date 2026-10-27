param(
    [string]$Executable = 'dist\experiments\no-cusolvermg-20261022-125001-723\NeuralHeat Studio\NeuralHeat Studio.exe'
)

# Test only the existing exclusion candidate. No downloads, install or rebuild.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$savedLocation = Get-Location
try {
    Set-Location -LiteralPath $projectRoot
    $Executable = (Resolve-Path -LiteralPath $Executable).Path
    $bundle = Split-Path -Parent $Executable
    if (Test-Path -LiteralPath (Join-Path $bundle '_internal\torch\lib\cusolverMg64_11.dll')) {
        throw 'This is not the cuSOLVERMg exclusion candidate.'
    }
    $output = Join-Path $projectRoot ('reports\redistribution\manual-beta-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '\runtime')
    & (Join-Path $projectRoot '.venv\Scripts\python.exe') scripts/test_redistribution_candidate.py --executable $Executable --output $output
    if ($LASTEXITCODE -ne 0) { throw "Desktop verification did not pass. Evidence: $output" }
    @{executable=$Executable;executable_sha256=(Get-FileHash -LiteralPath $Executable -Algorithm SHA256).Hash.ToLowerInvariant();verified_at=[DateTime]::UtcNow.ToString('o');runtime_directory=$output} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $output 'verified-candidate.json') -Encoding UTF8
    Write-Host "All frozen CPU/CUDA/worker/WebView2 checks passed. Evidence: $output" -ForegroundColor Green
} finally { Set-Location -LiteralPath $savedLocation }
