param(
    [string]$CandidateFile = 'reports\installer\20261027-093954-463\candidate.json',
    [switch]$AllUsers,
    [ValidateRange(1,120)][int]$WaitMinutes = 60
)

# Normal-Windows verification of the actual new installer. No rebuild or publish.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$savedLocation = Get-Location
try {
    Set-Location -LiteralPath $projectRoot
    $CandidateFile = (Resolve-Path -LiteralPath $CandidateFile).Path
    if ($AllUsers) {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            throw 'Open normal Windows PowerShell as Administrator for -AllUsers.'
        }
    }
    $deadline = [DateTime]::UtcNow.AddMinutes($WaitMinutes)
    Write-Host 'Waiting for the existing Inno build to finish; no partial installer will run.'
    do {
        $candidate = Get-Content -LiteralPath $CandidateFile -Raw | ConvertFrom-Json
        if (Test-Path -LiteralPath (Join-Path $candidate.report_directory 'build-failure.json')) {
            throw 'Installer build failed; inspect its build-failure.json.'
        }
        if ($candidate.status -in @('built_not_install_verified','verified') -and $candidate.installer_sha256) { break }
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Installer is not ready; nothing installed.' }
        Start-Sleep -Seconds 5
    } while ($true)
    $bundle = Split-Path -Parent $candidate.source_executable
    if (Test-Path -LiteralPath (Join-Path $bundle '_internal\torch\lib\cusolverMg64_11.dll')) {
        throw 'This is the old retained-Mg payload, not the beta candidate.'
    }
    if ((Get-FileHash -LiteralPath $candidate.installer -Algorithm SHA256).Hash.ToLowerInvariant() -ne $candidate.installer_sha256) {
        throw 'Installer differs from its completed build record.'
    }
    & (Join-Path $PSScriptRoot 'test_installer.ps1') -CandidateFile $CandidateFile -AllUsers:$AllUsers -TestDesktopShortcut -TestUninstall
    if (-not $?) { throw 'Actual installation verification did not pass.' }
    Write-Host 'Final installer verified, including real desktop, CPU/CUDA, worker, shortcuts and uninstall. Original builds and personal data are preserved.' -ForegroundColor Green
} finally { Set-Location -LiteralPath $savedLocation }
