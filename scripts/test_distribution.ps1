param([string]$CandidateFile)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not $CandidateFile) { $CandidateFile = Join-Path $projectRoot 'reports\distribution\candidate.json' }
$candidate = Get-Content -LiteralPath $CandidateFile -Raw | ConvertFrom-Json
$previousLocation = Get-Location

try {
    Set-Location -LiteralPath $projectRoot
    $executable = Join-Path $candidate.extracted_bundle 'NeuralHeat Studio.exe'
    if (-not (Test-Path -LiteralPath $executable)) { throw 'Candidate extraction is not ready. Complete compression and extraction first.' }
    & $pythonExe scripts/verify_distribution.py --integrity-only --audit $candidate.audit_manifest --extracted $candidate.extracted_bundle
    if ($LASTEXITCODE -ne 0) { throw 'Candidate extraction integrity failed.' }
    $runtimeError = $null
    try {
        & (Join-Path $PSScriptRoot 'test_desktop.ps1') -Executable $executable -ReportDirectory $candidate.report_directory
    } catch { $runtimeError = $_ }
    # Record measured size, hashes and actual partial test results even on failure.
    & $pythonExe scripts/verify_distribution.py --archive $candidate.archive --audit $candidate.audit_manifest --extracted $candidate.extracted_bundle --test-reports $candidate.report_directory --output $candidate.report_directory --original-zip (Join-Path $projectRoot 'NeuralHeat-Studio-Windows.zip')
    $verificationCode = $LASTEXITCODE
    Copy-Item -LiteralPath (Join-Path $candidate.report_directory 'distribution.json') -Destination (Join-Path (Split-Path $candidate.archive) 'distribution.json')
    Copy-Item -LiteralPath (Join-Path $candidate.report_directory 'distribution.md') -Destination (Join-Path (Split-Path $candidate.archive) 'distribution.md')
    if ($runtimeError) { throw $runtimeError }
    if ($verificationCode -ne 0) { throw 'Distribution is not fully verified below 1.9 GiB. Review distribution.json.' }
    Write-Host "Verified extracted portable package: $($candidate.archive)" -ForegroundColor Green
} finally { Set-Location -LiteralPath $previousLocation }
