# First public GitHub release

Publication preparation changes documentation, ignore rules, CI metadata and additive audit/capture/notice tools. It does not rebuild the software, run a new scientific experiment, remove local files or push anything.

## Source repository

There is no project `.git` directory or enclosing Git repository in the inspected workspace. Consequently there are **no tracked files or Git history to inspect**. The audit does not initialize the project or stage files. It creates a disposable Git metadata directory under ignored `.cache/` solely to evaluate the actual ignore rules. If a repository/history is later added, rerun the audit; it also checks tracked-but-ignored paths and historical blobs.

The prospective source tree is small: approximately **3.3 MiB with screenshots and retained notices**, including complete retained license texts. Exact current counts, sizes, candidate paths, hashes, secret-pattern findings and ignore checks are in local `.cache/publication-audit/audit.json`. Run:

```powershell
.\.venv\Scripts\python.exe scripts/audit_publication.py
```

The initial candidate scan found no credential-pattern matches and no files above 5 MiB. One maintainer-specific Windows path in installer documentation was replaced by `%LOCALAPPDATA%`. Keep upstream copyright-holder names and license notices; they are attribution, not leaked project credentials. Pattern scanning covers prospective text files and tracked history, not every possible secret encoding or all ignored environments.

Ready-to-commit material includes:

- `src/`, `tests/`, `configs/`, existing build/CLI scripts and the complete React source.
- `desktop/` packaging definitions, icon resources, `pyproject.toml`, npm manifests and `package-lock.json`.
- `.gitignore`, CI workflows, MIT `LICENSE`, README and technical documentation.
- Curated `reports/benchmark.json`, `.csv`, `.md`, `evaluation.json`, `models/training.json` and the three scientific PNGs.
- Four inspected actual interface screenshots and lossless compression provenance; retained `docs/licenses/` and third-party review.

Ignored and preserved locally: `.venv`, caches, `node_modules`, `dist`, `build`, datasets, checkpoint binaries, runs, archives, EXEs/installers, signing keys, environment files and non-curated machine/build reports. No Git LFS is required for the proposed source tree. Ignoring a path does not remove it from an existing Git index; the auditor reports that situation rather than silently changing history.

## Windows verification provenance

The maintainer reports that Windows installation and application verification now pass. The saved original portable-release CPU/CUDA/WebView2 tests also pass. The local installer test report under `reports/installer/latest.json` still points to the earlier restricted-executor failure: it unpacked all 2,799 application files, could not write Start Menu/uninstall-registry entries (Windows error 5), and rolled back. That historical report has not been rewritten to claim a passing test.

The [dated maintainer confirmation](verification/windows-release.md) records successful Windows verification without inventing individual automated outcomes. Detailed normal-Windows output can also be archived with the release when available. This does not require a rebuild. The installer and original model/report hashes are preserved. Maintainer confirmation is distinct from a fresh automated test performed during source preparation.

## Release assets, separate from Git

| Asset | Existing local location | Bytes |
|---|---|---:|
| Full Windows installer | `dist/installer/20261022-102027-253/NeuralHeat-Studio-Setup.exe` | 1,863,668,204 |
| Reference CNN checkpoint copy | `dist/release-support/best.pt` | 385,883 |
| Added third-party notice attachment | `dist/release-support/NeuralHeat-Studio-Third-Party-Notices.txt` | see generated asset manifest |
| Matching certifi covered source | `dist/release-support/NeuralHeat-Studio-Certifi-2026.4.22-Source.zip` | see generated asset manifest |
| Checksum manifest | `dist/release-support/SHA256SUMS.txt` | small text |

The notice/source attachments are additive and mandatory accompanying release materials. Their current exact sizes and hashes are in local `dist/release-support/release-assets.json` and `SHA256SUMS.txt`. The installer, original checkpoint, original portable folder and scientific evidence are not modified. The old 2.886 GB ZIP is excluded and exceeds the release-asset limit; publish the smaller setup EXE instead. Release assets are prepared, not uploaded. Use [release note draft](RELEASE_NOTES.md) only after resolving the remaining binary obligations.

Installer SHA256:

```text
861038b7f183f936db1a545d20d148c113fc31c00ae62ba1a00a043a0b8e64a9
```

Checkpoint SHA256:

```text
d5e2d5a88c8666101279d696f04aa32c53159399938de126642e3e745c4429d2
```

## Remaining publication checks

1. Screenshot integration is complete for the available captures, as approved by the maintainer: Overview, Physics, Network Explorer and native startup. [Manual provenance](screenshots/provenance.json) records dimensions, hashes and pixel-identical compression. Training/Latency page captures were not supplied; there are no placeholder references. These are manual captures, not an automated checkpoint/API test record.
2. [Third-party review](../THIRD_PARTY_NOTICES.md) now includes full frontend, exact WebView2 SDK, OpenSSL and NVIDIA notices plus matching certifi covered source. Remaining binary gates: establish the publisher's actual licensed Visual Studio/Build Tools edition and runtime provenance (including NumPy's older renamed DLL), obtain matching redistribution evidence for cuSOLVER Mg, and deliver the accompanying notices/source with the installer. No registered IDE/Build Tools installation was detected locally. Individual Community eligibility and source audit success do not establish binary entitlement.
3. Include the dated maintainer verification note; optionally archive detailed normal-Windows test output. The older restricted report remains private and unchanged.
4. Decide the public repository URL and release tag, initialize Git when ready, review `git status` / staged changes, and enable GitHub secret scanning/push protection where available. No repository, commit, remote, tag or push has been created automatically.

Code signing is not configured; the current installer is unsigned. WebView2 is an external prerequisite and a compatible NVIDIA driver is required for CUDA. Python dependencies use compatibility ranges; the recorded scientific environment is evidence rather than a universally reproducible package lock. CI workflow changes have been checked locally but GitHub Actions itself has not run in this workspace.

## Commit review when the remaining checks are complete

These are manual instructions; publication preparation has not executed them against the project:

```powershell
git init -b main
.\.venv\Scripts\python.exe scripts/audit_publication.py
git add .
git status --short
git diff --cached --stat
git diff --cached --check
# Review the staged files, then create the first commit when satisfied.
```

The source audit should pass before staging. Confirm that no `dist`, `build`, `.venv`, dataset, checkpoint binary, archive or installer appears in the staged list. Create the remote and upload release assets yourself after the licensing checks; no automatic push command is provided.
