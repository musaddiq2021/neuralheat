# NeuralHeat Studio v1.0.0-beta.1

**Completed and ready for upload.** The actual installed Mg-free application
passed all checks in [windows-beta.json](verification/windows-beta.json).
Installer: `dist/releases/v1.0.0-beta.1/NeuralHeat-Studio-Setup.exe`,
1,813,363,530 bytes (1.813 GB / 1.689 GiB). SHA256 and all accompanying assets are
in that folder's `SHA256SUMS.txt` and `release-manifest.json`. No tag/push/upload
was performed. The procedures below reproduce the completed work.

This procedure uses the existing Mg-free desktop candidate and preserves the
model, checkpoint, scientific reports, interface and original installer. It
does not require retraining or another React/PyInstaller build.

## Current measured status

On 27 October the existing candidate passed frozen CPU and CUDA/worker checks
again: solver agreement, inference, real activations, isolated smoke training,
cancellation, benchmark generation and all 68 packaged scientific asset hashes.
No Mg library or fallback to the original build/venv was observed. Its real
WebView2 test could not create a controller in the restricted executor
(`0x8000FFFF`). The later actual installed application passed those desktop
checks in normal Windows; the restricted failure was not rewritten as a pass.

The Microsoft review is now resolved: the exact official 14.40 package supplies
a byte-identical NumPy runtime, and the accepted Community 2026 terms and runtime
EULA are archived and reviewed. No DLL was replaced. The following reproduces
the completed evidence download; it does not need to be repeated for this build:

```powershell
cd D:\neuralheat
.\scripts\fetch_release_licences.ps1
```

The downloader installs nothing. Raw comparison evidence is retained under
`.cache/licensing/runtime-14.40-evidence-focused`; original documents and public
hash/provenance records are under `docs/licenses/`.

## Review the actual Microsoft documents and bytes

The completed archive/comparison can be reproduced with:

```powershell
.\.venv\Scripts\python.exe scripts/archive_community_licence.py `
  --source .cache/licensing/Visual_Studio_2026-License-Community_ENU.docx
.\.venv\Scripts\python.exe scripts/inspect_msvc_runtime.py `
  --installer .cache/licensing/VC_redist.x64-14.40.33810.exe `
  --output .cache/licensing/runtime-14.40-evidence
```

Use a fresh output directory when repeating extraction. The inspector verifies
Microsoft's pinned installer hash and uses Windows CAB extraction; it does not
execute the runtime installer or replace NumPy's DLL. Review the actual
Community distributable-code conditions and embedded runtime terms, then
record the applicable grant and exact-byte comparison in the existing MSVC
provenance/review. No second acceptance, second Visual Studio installation or
vendor permission letter is required merely for archiving the terms. A vendor
enquiry is a fallback only if the reviewed terms genuinely leave a gap.

## Compile and verify the installer

For this release the new Inno installer was compiled from the already tested
backend payload, with the source-only WebView2 failure explicitly recorded.
Its actual installed GUI test subsequently passed. A second portable GUI test
is optional. To reproduce installation verification, run from elevated normal
Windows PowerShell:

```powershell
.\scripts\verify_beta_installer.ps1 -AllUsers
```

The wrapper waits for this exact build to finish and verifies its hash before
execution. It does not run a partial EXE or rebuild anything. It tests actual
installation, desktop pages, CPU/CUDA, worker, shortcuts, AppData and uninstall.

For a future build with passing portable evidence, the combined procedure is
also available, substituting that evidence directory:

```powershell
.\scripts\finish_cusolvermg_candidate.ps1 `
  -Executable 'dist\experiments\no-cusolvermg-20261022-125001-723\NeuralHeat Studio\NeuralHeat Studio.exe' `
  -RuntimeVerificationDirectory 'reports\redistribution\manual-beta-<id>\runtime' `
  -AllUsers
```

This reuses the executable-hash-bound runtime evidence, prepares current notices
and certifi source, includes them in the candidate, and compiles a new
timestamped Inno installer. The installation licence page includes the retained
MIT and third-party binary conditions. It then tests a real Program Files
installation, shortcuts, registration, CPU/CUDA, training, four desktop pages,
AppData and uninstall preservation. It refuses to overwrite an existing
personal installation. `-BuildOnly` is available when installation testing must
run separately. No result is marked verified just because compilation succeeds.

The final source review records the measured passing installation evidence and clears only
the satisfied items in `docs/licenses/redistribution-review.json`. Retain full
notices and certifi source; they are distribution materials, not an additional
approval requirement. Code signing is optional for this beta. WebView2 and a
compatible GPU driver remain documented system prerequisites.

## Stage the GitHub prerelease

```powershell
.\.venv\Scripts\python.exe scripts/audit_publication.py
.\.venv\Scripts\python.exe scripts/prepare_beta_release.py
```

The release preparer checks the actual installation report and installer
SHA256, excludes a retained-Mg source, preserves the reference checkpoint, and
stages the verified assets under `dist/releases/v1.0.0-beta.1/`. It writes
`SHA256SUMS.txt`, measured release notes and `release-manifest.json`. Before
verification completes, that manifest explicitly says `draft_awaiting_evidence`
and `upload_ready_installer` is null: the original installer is not relabelled
as a cleared beta.

Review/commit the source and create the intended release tag yourself. Upload
the prepared assets as a GitHub **prerelease**, or use the optional generated
`CREATE_GITHUB_DRAFT.ps1` with GitHub CLI to create a private draft. No script in
this preparation automatically commits, tags, pushes or publishes.
