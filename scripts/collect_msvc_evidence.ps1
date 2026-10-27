param(
    [string]$VisualStudioRoot,
    [string]$AcceptanceRecord,
    [string]$OutputDirectory
)

# Read-only collection. Does not acquire or accept a license or install software.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $projectRoot ('.cache\msvc-evidence\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
}
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Use a fresh output directory.' }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$instances = @()
if (Test-Path -LiteralPath $vswhere) {
    $raw = & $vswhere -all -products '*' -format json -utf8
    if ($LASTEXITCODE -ne 0) { throw 'vswhere failed.' }
    $raw | Set-Content -LiteralPath (Join-Path $OutputDirectory 'vswhere.json') -Encoding UTF8
    # PowerShell 5.1 can otherwise preserve the JSON array as one nested object.
    $instances = @((($raw -join "`n") | ConvertFrom-Json) | ForEach-Object { $_ })
    if (-not $VisualStudioRoot -and $instances.Count -eq 1) { $VisualStudioRoot = $instances[0].installationPath }
}
$manifest = Get-Content -LiteralPath (Join-Path $projectRoot 'dist\desktop\latest.json') -Raw | ConvertFrom-Json
$bundle = Split-Path -Parent $manifest.executable
$dlls = @(
    '_internal\msvcp140.dll',
    '_internal\vcruntime140.dll',
    '_internal\vcruntime140_1.dll',
    '_internal\numpy.libs\msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll'
)
$referenceFiles = @()
if ($VisualStudioRoot) {
    $VisualStudioRoot = (Resolve-Path -LiteralPath $VisualStudioRoot).Path
    $redist = Join-Path $VisualStudioRoot 'VC\Redist'
    if (-not (Test-Path -LiteralPath $redist)) { throw 'The specified Visual Studio copy has no VC\Redist tree. Install the applicable C++ redist components.' }
    $referenceFiles = @(Get-ChildItem -LiteralPath $redist -Recurse -File -Filter '*.dll' | Where-Object {
        $_.FullName -notmatch 'debug_nonredist' -and $_.VersionInfo.OriginalFilename -in @('msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll')
    })
}
$rows = foreach ($relative in $dlls) {
    $file = Get-Item -LiteralPath (Join-Path $bundle $relative)
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
    $matches = @($referenceFiles | Where-Object {
        $_.Length -eq $file.Length -and (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -eq $hash
    } | Select-Object -ExpandProperty FullName)
    [ordered]@{
        relative_path=$relative; version=$file.VersionInfo.FileVersion
        original_filename=$file.VersionInfo.OriginalFilename; bytes=$file.Length; sha256=$hash
        signature=$signature.Status.ToString(); signer=$signature.SignerCertificate.Subject
        matching_licensed_redist_paths=$matches
    }
}
$assertion = $null
if ($AcceptanceRecord) {
    $recordPath = (Resolve-Path -LiteralPath $AcceptanceRecord).Path
    $assertion = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
    foreach ($field in @('edition','version','terms_url','terms_file','individual_project_statement')) {
        if (-not $assertion.$field) { throw "Acceptance record is missing $field" }
    }
    if (-not $assertion.accepted_on -and -not $assertion.acceptance_confirmed_on) {
        throw 'Acceptance record needs accepted_on or acceptance_confirmed_on; do not invent an acceptance date.'
    }
    $terms = (Resolve-Path -LiteralPath $assertion.terms_file).Path
    Copy-Item -LiteralPath $terms -Destination (Join-Path $OutputDirectory ([IO.Path]::GetFileName($terms)))
    $assertion | Add-Member -NotePropertyName terms_sha256 -NotePropertyValue ((Get-FileHash -LiteralPath $terms -Algorithm SHA256).Hash.ToLowerInvariant()) -Force
}
$result = [ordered]@{
    status='action_required_or_review'; collected_at=[DateTime]::UtcNow.ToString('o')
    detected_instances=$instances; selected_visual_studio_root=$VisualStudioRoot
    publisher_assertion=$assertion; dlls=@($rows)
    license_accepted_by_this_script=$false; public_distribution_authorized=$false
    explanation='Installation, publisher acceptance and exact file provenance are separate evidence. A human must review the applicable terms; this collector never grants redistribution rights.'
}
$result | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'evidence.json') -Encoding UTF8
Write-Host "Evidence saved: $OutputDirectory"
Write-Host 'This script did not accept a license or grant redistribution rights.'
