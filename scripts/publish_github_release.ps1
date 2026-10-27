param([string]$SourceCommitRecord)

# Approved publication only: no build, training, model or application edits.
# Run in normal Windows PowerShell after GitHub CLI authentication.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $SourceCommitRecord) { $SourceCommitRecord = Join-Path $projectRoot '.cache\github-publication\source-commit.json' }
$savedLocation = Get-Location

function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Program ($LASTEXITCODE)" }
}

try {
    Set-Location -LiteralPath $projectRoot
    $ghCommand = Get-Command gh.exe -ErrorAction SilentlyContinue
    $ghExe = if ($ghCommand) { $ghCommand.Source } else { Join-Path $env:ProgramFiles 'GitHub CLI\gh.exe' }
    if (-not (Test-Path -LiteralPath $ghExe)) { throw 'Install GitHub CLI, open a new PowerShell, and run gh auth login first.' }
    Invoke-Checked $ghExe @('auth','status','--hostname','github.com')
    $source = Get-Content -LiteralPath $SourceCommitRecord -Raw | ConvertFrom-Json
    $repository = 'musaddiq2021/neuralheat'
    $tag = 'v1.0.0-beta.1'
    $expectedHash = 'ecf3f57dcc2f8b50144c42e505559f71550d1f75466c3734aab16ec78d69171f'
    if ($source.repository -ne $repository -or $source.branch -ne 'main' -or $source.commit_sha -notmatch '^[a-f0-9]{40}$') {
        throw 'Unexpected source publication record.'
    }
    $releaseRoot = Join-Path $projectRoot "dist\releases\$tag"
    $manifest = Get-Content -LiteralPath (Join-Path $releaseRoot 'release-manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.status -ne 'ready_for_upload') { throw 'The approved release is not ready.' }
    Invoke-Checked (Join-Path $projectRoot '.venv\Scripts\python.exe') @('scripts/verify_release_source.py')
    foreach ($asset in $manifest.assets) {
        $path = Join-Path $releaseRoot $asset.name
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $asset.sha256) {
            throw "Release asset changed: $($asset.name)"
        }
    }
    if ((Get-FileHash -LiteralPath (Join-Path $releaseRoot 'NeuralHeat-Studio-Setup.exe') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) {
        throw 'The installer is not the approved binary.'
    }
    Invoke-Checked $ghExe @('auth','setup-git','--hostname','github.com')
    Invoke-Checked 'git' @('fetch','origin','main','--tags')
    if ((& git branch --show-current).Trim() -ne 'main') { throw 'Use the existing main worktree.' }
    $head = (& git rev-parse HEAD).Trim()
    $publicationHead = (& git rev-parse 'origin/main').Trim()
    Invoke-Checked 'git' @('merge-base','--is-ancestor',$source.commit_sha,$publicationHead)
    # A publication-helper correction may follow the frozen release source.
    # Keep the tag/provenance pinned; reject any change to application or assets.
    $followupPaths = @(& git diff --name-only $source.commit_sha $publicationHead)
    if ($LASTEXITCODE -ne 0 -or @($followupPaths | Where-Object { $_ -ne 'scripts/publish_github_release.ps1' }).Count) {
        throw 'Main contains changes beyond the publication helper; review before publishing the pinned release.'
    }
    Invoke-Checked 'git' @('merge-base','--is-ancestor',$head,$publicationHead)
    # The source was committed through GitHub because this executor could not
    # write .git. Fast-forward local metadata; --mixed changes no working files.
    if ($head -ne $publicationHead) { Invoke-Checked 'git' @('reset','--mixed',$publicationHead) }
    $dirty = @(& git status --porcelain)
    if ($dirty.Count) { throw 'Working source differs from the published commit. Review git status before tagging.' }
    Invoke-Checked 'git' @('push','origin','main')
    & git show-ref --verify --quiet "refs/tags/$tag"
    if ($LASTEXITCODE -eq 0) {
        if ((& git rev-parse "$tag^{commit}").Trim() -ne $source.commit_sha) { throw 'Existing tag identifies different source; no force update performed.' }
    } else {
        Invoke-Checked 'git' @('tag','-a',$tag,$source.commit_sha,'-m',"NeuralHeat Studio $tag")
    }
    Invoke-Checked 'git' @('push','origin',"refs/tags/$tag")

    $notes = Join-Path $releaseRoot 'release-notes.md'
    $body = [IO.File]::ReadAllText($notes)
    $body = $body.Replace('Prepared locally; no tag, upload or remote release was created.', 'Published as an approved Windows prerelease.')
    $commitLink = "https://github.com/$repository/commit/$($source.commit_sha)"
    if (-not $body.Contains($commitLink)) { $body += "`r`nSource commit: $commitLink`r`n" }
    [IO.File]::WriteAllText($notes,$body,(New-Object Text.UTF8Encoding($false)))
    $provenancePath = Join-Path $releaseRoot 'release-provenance.json'
    $provenance = [ordered]@{
        tag=$tag;source_commit=$source.commit_sha;source_tree=$source.tree_sha
        installer_sha256=$expectedHash;installer_bytes=1813363530
        source_correspondence_record="https://github.com/$repository/blob/$($source.commit_sha)/docs/verification/release-source.json"
        installed_verification_record="https://github.com/$repository/blob/$($source.commit_sha)/docs/verification/windows-beta.json"
        unsigned_installer=$true;webview2_required=$true;cuda_driver_required=$true
    }
    [IO.File]::WriteAllText($provenancePath,($provenance | ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($false)))
    $assetNames = @($manifest.assets | ForEach-Object { $_.name }) + @('release-notes.md','release-provenance.json')
    $checksums = @()
    $uploadExpected = @{}
    foreach ($name in $assetNames) {
        $file = Get-Item -LiteralPath (Join-Path $releaseRoot $name)
        $sha = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $checksums += "$sha  $name"
        $uploadExpected[$name] = @{sha256=$sha;bytes=$file.Length}
    }
    [IO.File]::WriteAllText((Join-Path $releaseRoot 'SHA256SUMS.txt'),(($checksums -join "`n")+"`n"),(New-Object Text.UTF8Encoding($false)))
    $assetNames += 'SHA256SUMS.txt'
    $checksumFile = Get-Item -LiteralPath (Join-Path $releaseRoot 'SHA256SUMS.txt')
    $uploadExpected['SHA256SUMS.txt'] = @{sha256=(Get-FileHash -LiteralPath $checksumFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant();bytes=$checksumFile.Length}

    $releaseList = & $ghExe api "repos/$repository/releases?per_page=100"
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect existing releases before publication.' }
    $matches = @((($releaseList -join "`n") | ConvertFrom-Json) | ForEach-Object { $_ } | Where-Object { $_.tag_name -eq $tag })
    $exists = $matches.Count -eq 1
    $existing = if ($exists) { $matches[0] } else { $null }
    if (-not $exists) {
        Invoke-Checked $ghExe @('release','create',$tag,'--repo',$repository,'--verify-tag','--draft','--prerelease','--title',"NeuralHeat Studio $tag",'--notes-file',$notes)
    }
    # Upload while private. An already-public matching release is verified below,
    # never silently replaced or made private by a retry.
    if (-not $exists -or $existing.draft) {
        foreach ($name in $assetNames) {
            $savedAsset = @($existing.assets | Where-Object { $_.name -eq $name })
            if ($savedAsset.Count -eq 1 -and $savedAsset[0].state -eq 'uploaded' -and
                $savedAsset[0].size -eq $uploadExpected[$name].bytes -and
                $savedAsset[0].digest -eq ('sha256:'+$uploadExpected[$name].sha256)) {
                Write-Host "Already verified on GitHub: $name"
                continue
            }
            $uploaded = $false
            for ($attempt=1; $attempt -le 3; $attempt++) {
                & $ghExe release upload $tag (Join-Path $releaseRoot $name) --repo $repository --clobber
                if ($LASTEXITCODE -eq 0) { $uploaded=$true;break }
                if ($attempt -lt 3) { Start-Sleep -Seconds 5 }
            }
            if (-not $uploaded) { throw "Upload failed: $name. Release remains draft; rerun safely." }
        }
    }
    # GitHub's by-tag endpoint excludes drafts. Resolve the ID from the list,
    # then inspect that release before making anything public.
    $verifyList = & $ghExe api "repos/$repository/releases?per_page=100"
    if ($LASTEXITCODE -ne 0) { throw 'Cannot find the uploaded draft.' }
    $verifyMatches = @((($verifyList -join "`n") | ConvertFrom-Json) | ForEach-Object { $_ } | Where-Object { $_.tag_name -eq $tag })
    if ($verifyMatches.Count -ne 1) { throw 'Expected exactly one release for the approved tag.' }
    $releaseId = $verifyMatches[0].id
    $remoteText = & $ghExe api "repos/$repository/releases/$releaseId"
    if ($LASTEXITCODE -ne 0) { throw 'Cannot verify uploaded release assets.' }
    $remote = $remoteText | ConvertFrom-Json
    foreach ($name in $assetNames) {
        $match = @($remote.assets | Where-Object { $_.name -eq $name })
        if ($match.Count -ne 1 -or $match[0].size -ne $uploadExpected[$name].bytes) { throw "Remote asset missing or wrong size: $name" }
        if ($match[0].digest -and $match[0].digest -ne ('sha256:'+$uploadExpected[$name].sha256)) { throw "Remote asset digest differs: $name" }
    }
    Invoke-Checked $ghExe @('release','edit',$tag,'--repo',$repository,'--draft=false','--prerelease','--notes-file',$notes)
    $publicText = & $ghExe api "repos/$repository/releases/tags/$tag"
    if ($LASTEXITCODE -ne 0) { throw 'Cannot confirm published release.' }
    $public = $publicText | ConvertFrom-Json
    if ($public.draft -or -not $public.prerelease) { throw 'Release is not the approved public prerelease.' }
    $publicText | Set-Content -LiteralPath (Join-Path $projectRoot '.cache\github-publication\published-release.json') -Encoding UTF8
    Write-Host "Published prerelease: $($public.html_url)" -ForegroundColor Green
} finally { Set-Location -LiteralPath $savedLocation }
