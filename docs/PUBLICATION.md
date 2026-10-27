# NeuralHeat Studio v1.0.0-beta.1 publication record

**Approved for publication, 27 October 2026.** The Mg-free installer passed actual Windows Program Files installation and all installed-application checks. Microsoft licence/provenance review is complete. Original builds, checkpoint, scientific reports and UI are preserved. The [source correspondence record](verification/release-source.json) confirms byte-identical application Python and matching compiled UI/scientific assets. Packaging/licence/publication materials were finalised after freezing without rebuilding the application.

## Source repository

The source tree is approximately **3.6 MiB**, including real screenshots, source, tests, packaging tools and retained licences. The publication audit checks prospective files, tracked-but-ignored paths, credentials, large files, documentation links and Git history. It found no credential matches, personal-path findings, tracked ignored files or blobs above the configured size threshold. Exact current counts are in ignored `.cache/publication-audit/audit.json`.

```powershell
.\.venv\Scripts\python.exe scripts/audit_publication.py
```

Environments, node_modules, build/dist trees, datasets, caches, checkpoint binaries, runtime logs, raw test runs and application archives/installers stay outside Git. Curated scientific JSON/CSV/Markdown and figures remain in source; the reference checkpoint is a separate release asset. No Git LFS is needed. Source audit success does not replace application tests or legal review.

## Actual Windows verification

The [public verification record](verification/windows-beta.json) summarizes the real elevated-Windows run. Its raw evidence remains under `reports/installer/20261027-093954-463/installation-20261027-100644-302/`.

- All **2,801 application files** match the source payload before and after execution.
- Installed CPU operation and automatic CUDA selection pass on the RTX 4070 Laptop GPU.
- Approved smoke training and cancellation pass in isolated AppData; original scientific outputs and the reference checkpoint remain unchanged.
- Physics, Network Explorer, Training Control Room, Latency Lab and native resizing pass through the actual WebView2 window.
- Program Files installation, uninstall registration, Start Menu/desktop shortcuts and AppData storage pass.
- Uninstall removes the test installation and preserves personal data.
- **62 Python tests**, Ruff, PowerShell syntax checks and guarded collection equivalence checks pass.

Earlier restricted WebView2/controller and Start Menu/registry failures remain historical evidence, not rewritten passing reports. The [original maintainer attestation](verification/windows-release.md) concerns the older build; this beta has its own actual installer evidence.

## Upload assets

Prepared folder: `D:\neuralheat\dist\releases\v1.0.0-beta.1`.

| Asset | Bytes |
|---|---:|
| `NeuralHeat-Studio-Setup.exe` | 1,813,363,530 |
| `best.pt` | 385,883 |
| `NeuralHeat-Studio-Third-Party-Notices.txt` | 1,515,191 |
| `NeuralHeat-Studio-Certifi-2026.4.22-Source.zip` | 139,214 |
| `SHA256SUMS.txt` | generated text manifest |

The installer is **1.813 GB / 1.689 GiB**, below the GitHub asset limit and the 1.9 GiB target. Its complete application tree is 4,338,077,017 bytes. Setup makes no downloads and includes the checkpoint, matching datasets, interface and CPU/CUDA runtimes. WebView2 and a compatible NVIDIA driver for CUDA remain system prerequisites. Signing is not configured; an unsigned-publisher/SmartScreen prompt is a documented beta limitation, not an unresolved redistribution question.

Installer SHA256:

```text
ecf3f57dcc2f8b50144c42e505559f71550d1f75466c3734aab16ec78d69171f
```

Reference checkpoint SHA256:

```text
d5e2d5a88c8666101279d696f04aa32c53159399938de126642e3e745c4429d2
```

The old retained-Mg installer stays at `dist/installer/20261022-102027-253/NeuralHeat-Studio-Setup.exe`, unchanged SHA256 `861038b7f183f936db1a545d20d148c113fc31c00ae62ba1a00a043a0b8e64a9`. It is not the beta upload asset. The large older application ZIP remains local.

## Licence and packaging disposition

The [third-party review](../THIRD_PARTY_NOTICES.md) records the accepted Community licence, full archived documents and exact official provenance for all four MSVC DLLs. NumPy's hash-named file was not replaced: it exactly matches the signed official 14.40 runtime package. Redistribution relies on the licensed Visual Studio grant, not the runtime installation EULA alone.

The beta omits the entire unused Mg component through the [guarded policy](../desktop/freeze_policy.py). Ordinary CUDA/cuDNN and their notices remain. The policy matches the tested exclusion and refuses unsafe imports or an unreviewed CUDA-wheel exclusion. No Mg vendor permission is needed for a component not distributed. Full notices, protective installation terms and matching certifi source are inside the installer and accompany the release; keep them with redistribution.

## Prepare and publish

The [beta procedure](BETA_RELEASE.md) reproduces the evidence and packaging. To restage the verified assets:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_beta_release.py
```

`release-manifest.json` reports `ready_for_upload`, hashes and exact paths. `release-notes.md` is the prepared prerelease body. The optional `CREATE_GITHUB_DRAFT.ps1` verifies asset hashes and uses GitHub CLI to create a private draft only after the intended tag exists. Browser upload through GitHub Releases is also sufficient; GitHub CLI is not an end-user dependency.

Review and commit the source changes before tagging. These are manual instructions; no command below has been executed automatically:

```powershell
git status --short
git add .gitattributes README.md THIRD_PARTY_NOTICES.md docs desktop scripts tests/test_beta_release.py
git diff --cached --stat
git diff --cached --check
# Review, commit, and create the v1.0.0-beta.1 tag when satisfied.
```

The maintainer approved source commit/push and public prerelease publication. The connected GitHub integration can commit the audited source when the local executor cannot write `.git`. `scripts/publish_github_release.ps1` then fast-forwards local Git metadata without changing working files, tags the exact source commit, uploads the verified files into a draft, checks remote asset sizes/digests, and publishes it as a prerelease. It never rebuilds or edits the application. Publication results are recorded separately under ignored `.cache/github-publication/` and in the release's `release-provenance.json` asset. No runtime/licence or installation-verification item remains open for this beta payload.
