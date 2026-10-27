param(
    [string]$CandidateFile,
    [string]$InstallDirectory,
    [switch]$AllUsers,
    [switch]$TestDesktopShortcut,
    [switch]$TestUninstall
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not $CandidateFile) { $CandidateFile = Join-Path $projectRoot 'reports\installer\candidate.json' }
$CandidateFile = (Resolve-Path -LiteralPath $CandidateFile).Path
$candidate = Get-Content -LiteralPath $CandidateFile -Raw | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $candidate.installer)) { throw 'Build the installer before testing it.' }
$testId = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$reportRoot = Join-Path $candidate.report_directory "installation-$testId"
$testRoot = Join-Path $projectRoot ".cache\installer-tests\$testId"
New-Item -ItemType Directory -Path $reportRoot,$testRoot | Out-Null
$registrySubkey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6E55B462-28F0-4C8A-98C5-E896B4D52631}_is1'
$registryPath = if ($AllUsers) { "Registry::HKEY_LOCAL_MACHINE\$registrySubkey" } else { "Registry::HKEY_CURRENT_USER\$registrySubkey" }
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if ($AllUsers -and -not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this test from an elevated Windows PowerShell to verify a Program Files installation with -AllUsers.'
}
# A release test must never replace an existing personal installation.
foreach ($root in @('HKEY_CURRENT_USER','HKEY_LOCAL_MACHINE')) {
    if (Test-Path -LiteralPath "Registry::$root\$registrySubkey") {
        throw 'NeuralHeat Studio is already installed. This isolated test refuses to replace that installation.'
    }
}
if (-not $InstallDirectory) {
    $InstallDirectory = if ($AllUsers) { Join-Path $env:ProgramFiles 'NeuralHeat Studio' } else { Join-Path $testRoot 'installed\NeuralHeat Studio' }
}
$InstallDirectory = [IO.Path]::GetFullPath($InstallDirectory)
if (Test-Path -LiteralPath $InstallDirectory) { throw "Test installation target already exists: $InstallDirectory" }
$programs = [Environment]::GetFolderPath($(if ($AllUsers) { 'CommonPrograms' } else { 'Programs' }))
$desktop = [Environment]::GetFolderPath($(if ($AllUsers) { 'CommonDesktopDirectory' } else { 'DesktopDirectory' }))
$groupName = 'NeuralHeat Studio'
$startShortcut = Join-Path $programs "$groupName\NeuralHeat Studio.lnk"
$desktopShortcut = Join-Path $desktop 'NeuralHeat Studio.lnk'
if (Test-Path -LiteralPath $startShortcut) { throw 'The Start Menu shortcut already exists; refusing to overwrite it.' }
if ($TestDesktopShortcut -and (Test-Path -LiteralPath $desktopShortcut)) { throw 'The desktop shortcut already exists; refusing to overwrite it.' }
$evidence = @{
    status='running'; install_directory=$InstallDirectory; installer=$candidate.installer
    install_scope=$(if ($AllUsers) { 'all_users_program_files' } else { 'current_user_isolated_directory' })
    uninstall_requested=[bool]$TestUninstall; desktop_shortcut_requested=[bool]$TestDesktopShortcut
    application_environment='No developer runtimes on PATH; HTTP proxies disabled; isolated LOCALAPPDATA'
}
$evidenceFile = Join-Path $reportRoot 'installation-evidence.json'
$previousLocation = Get-Location
$savedEnvironment = @{}
foreach ($name in @('PATH','PYTHONPATH','PYTHONHOME','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','LOCALAPPDATA','NEURALHEAT_PROJECT_ROOT','NEURALHEAT_FRONTEND_DIST')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name,'Process')
}
$failure = $null

function Invoke-Process([string]$program, [string[]]$arguments, [int]$timeout = 600000) {
    $process = Start-Process -FilePath $program -ArgumentList $arguments -WindowStyle Hidden -PassThru
    try {
        if (-not $process.WaitForExit($timeout)) {
            $process.Kill()
            throw "Process timed out: $program"
        }
        return $process.ExitCode
    } finally { $process.Dispose() }
}

function Assert-Shortcut([string]$path, [string]$target) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing shortcut: $path" }
    $shell = New-Object -ComObject WScript.Shell
    try {
        $shortcut = $shell.CreateShortcut($path)
        if ($shortcut.TargetPath -ine $target) { throw "Incorrect shortcut target: $path -> $($shortcut.TargetPath)" }
        return @{path=$path;target=$shortcut.TargetPath;working_directory=$shortcut.WorkingDirectory}
    } finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell) }
}

try {
    Set-Location -LiteralPath $projectRoot
    $scope = if ($AllUsers) { '/ALLUSERS' } else { '/CURRENTUSER' }
    $tasks = if ($TestDesktopShortcut) { '/TASKS="desktopicon"' } else { '/TASKS="!desktopicon"' }
    # The installer deliberately hides the group page; Inno ignores /GROUP in that mode.
    $arguments = @('/SP-','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',$scope,$tasks,('/DIR="'+$InstallDirectory+'"'),('/LOG="'+(Join-Path $reportRoot 'install.log')+'"'))
    $evidence.install_exit_code = Invoke-Process $candidate.installer $arguments 1200000
    if ($evidence.install_exit_code -ne 0) { throw "Installation failed ($($evidence.install_exit_code)). See $reportRoot\install.log" }
    $registered = Get-ItemProperty -LiteralPath $registryPath
    if ($registered.DisplayName -ne 'NeuralHeat Studio' -or $registered.InstallLocation.TrimEnd('\') -ine $InstallDirectory.TrimEnd('\')) {
        throw 'Windows uninstall registration does not match the installed application.'
    }
    $evidence.registration = @{status='passed';key=$registryPath;display_name=$registered.DisplayName;install_location=$registered.InstallLocation;uninstall_command=$registered.UninstallString}
    $installedExe = Join-Path $InstallDirectory 'NeuralHeat Studio.exe'
    $links = @(Assert-Shortcut $startShortcut $installedExe)
    if ($TestDesktopShortcut) { $links += Assert-Shortcut $desktopShortcut $installedExe }
    $evidence.shortcuts = @{status='passed';links=$links;desktop_tested=[bool]$TestDesktopShortcut}
    $integrityBefore = Join-Path $reportRoot 'installed-integrity-before.json'
    & $pythonExe scripts/installer_release.py verify --installed $InstallDirectory --manifest $candidate.source_manifest --output $integrityBefore
    if ($LASTEXITCODE -ne 0) { throw 'Installed payload integrity failed.' }
    $evidence.integrity_before = Get-Content -LiteralPath $integrityBefore -Raw | ConvertFrom-Json
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $env:PYTHONPATH = $null
    $env:PYTHONHOME = $null
    $env:NEURALHEAT_PROJECT_ROOT = $null
    $env:NEURALHEAT_FRONTEND_DIST = $null
    $env:HTTP_PROXY = 'http://127.0.0.1:9'
    $env:HTTPS_PROXY = 'http://127.0.0.1:9'
    $env:ALL_PROXY = 'http://127.0.0.1:9'
    $env:LOCALAPPDATA = Join-Path $testRoot 'AppData\Local'
    New-Item -ItemType Directory -Path $env:LOCALAPPDATA | Out-Null
    $expectedUser = Join-Path $env:LOCALAPPDATA 'NeuralHeat Studio'
    $evidence.test_appdata_directory = $expectedUser
    $runtime = @(
        @{name='installed-cpu';flags=@('--device','cpu')},
        @{name='installed-auto-worker';flags=@('--device','auto','--verify-worker')},
        @{name='installed-webview';flags=@('--device','auto','--ui-test')}
    )
    Set-Location -LiteralPath $testRoot
    $testErrors = @()
    foreach ($test in $runtime) {
        try {
            $report = Join-Path $reportRoot ($test.name+'.json')
            $testArguments = @('--self-test','--test-report',('"'+$report+'"')) + $test.flags
            $exitCode = Invoke-Process $installedExe $testArguments
            if ($exitCode -ne 0) { throw "$($test.name) failed with exit code $exitCode" }
            $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
            if ($result.status -ne 'passed' -or -not $result.frozen -or -not $result.backend_port_closed) { throw "$($test.name) frozen checks failed" }
            Write-Host "$($test.name) passed | $($result.device)" -ForegroundColor Green
        } catch {
            $testErrors += $_.Exception.Message
            Write-Warning $_.Exception.Message
        }
    }
    $evidence.runtime_errors = $testErrors
    $evidence.appdata_verified = (Test-Path -LiteralPath (Join-Path $expectedUser 'logs\desktop.log')) -and (Test-Path -LiteralPath (Join-Path $expectedUser 'runs\studio')) -and (Test-Path -LiteralPath (Join-Path $expectedUser 'cache'))
    # Restore the developer environment before running verification tools.
    foreach ($name in $savedEnvironment.Keys) { [Environment]::SetEnvironmentVariable($name,$savedEnvironment[$name],'Process') }
    Set-Location -LiteralPath $projectRoot
    $integrityAfter = Join-Path $reportRoot 'installed-integrity-after.json'
    & $pythonExe scripts/installer_release.py verify --installed $InstallDirectory --manifest $candidate.source_manifest --output $integrityAfter
    if ($LASTEXITCODE -ne 0) { throw 'Installed application files changed during execution.' }
    $evidence.integrity_after = Get-Content -LiteralPath $integrityAfter -Raw | ConvertFrom-Json
    if ($TestUninstall) {
        $marker = Join-Path $expectedUser 'settings\installer-preservation-check.txt'
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $marker) | Out-Null
        'This personal data must survive uninstall.' | Set-Content -LiteralPath $marker
        $uninstallExe = Join-Path $InstallDirectory 'unins000.exe'
        $uninstallExit = Invoke-Process $uninstallExe @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/LOG="'+(Join-Path $reportRoot 'uninstall.log')+'"'))
        # Inno's uninstaller can finish deleting itself shortly after the loader exits.
        $deadline = [DateTime]::UtcNow.AddSeconds(15)
        while ((Test-Path -LiteralPath $installedExe) -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 200 }
        $removed = -not (Test-Path -LiteralPath $installedExe) -and -not (Test-Path -LiteralPath $registryPath) -and -not (Test-Path -LiteralPath $startShortcut)
        $preserved = (Test-Path -LiteralPath $marker) -and (Get-Content -LiteralPath $marker -Raw).Contains('must survive uninstall')
        $evidence.uninstall = @{status=$(if ($uninstallExit -eq 0 -and $removed -and $preserved) { 'passed' } else { 'failed' });exit_code=$uninstallExit;personal_data_preserved=$preserved;application_removed=$removed}
    }
    $evidence.status = 'completed'
} catch {
    $failure = $_
    $evidence.status = 'failed'
    $evidence.error = $_.Exception.Message
} finally {
    foreach ($name in $savedEnvironment.Keys) { [Environment]::SetEnvironmentVariable($name,$savedEnvironment[$name],'Process') }
    Set-Location -LiteralPath $projectRoot
    $evidence | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $evidenceFile -Encoding UTF8
    & $pythonExe scripts/installer_release.py report --candidate $CandidateFile --evidence $evidenceFile --output $reportRoot
    $verificationCode = $LASTEXITCODE
    $result = Get-Content -LiteralPath (Join-Path $reportRoot 'installer.json') -Raw | ConvertFrom-Json
    if ($verificationCode -eq 0 -and $result.status -eq 'verified') {
        $candidate.status = 'verified'
        $candidate | Add-Member -NotePropertyName verified_report_directory -NotePropertyValue $reportRoot -Force
        $candidate | Add-Member -NotePropertyName source_desktop_verification_pending -NotePropertyValue $false -Force
        $candidate | Add-Member -NotePropertyName desktop_verification_basis -NotePropertyValue 'Actual installed WebView2 pages passed; installed/source payload hashes match. Earlier restricted source-window failures remain in their original reports.' -Force
        $candidate | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $CandidateFile -Encoding UTF8
        $activeCandidate = Join-Path $projectRoot 'reports\installer\candidate.json'
        if ((Get-Content -LiteralPath $activeCandidate -Raw | ConvertFrom-Json).build_id -eq $candidate.build_id) {
            $candidate | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $activeCandidate -Encoding UTF8
        }
    }
    $latest = @{installer=$candidate.installer;report_directory=$reportRoot;status=$result.status;candidate_file=$CandidateFile}
    $latest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectRoot 'reports\installer\latest.json') -Encoding UTF8
    Copy-Item -LiteralPath (Join-Path $reportRoot 'installer.json') -Destination (Join-Path (Split-Path -Parent $candidate.installer) 'installer.json')
    Copy-Item -LiteralPath (Join-Path $reportRoot 'installer.md') -Destination (Join-Path (Split-Path -Parent $candidate.installer) 'installer.md')
    Set-Location -LiteralPath $previousLocation
}
if ($failure) { throw $failure }
if ($verificationCode -ne 0) { throw "Installer is not fully verified. Review $reportRoot\installer.json" }
Write-Host "Installed application verified: $($candidate.installer)" -ForegroundColor Green
