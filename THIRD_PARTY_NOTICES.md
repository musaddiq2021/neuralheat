# Third-party notices and redistribution review

NeuralHeat's own source is [MIT licensed](LICENSE). Dependencies retain their licenses. This review concerns the existing verified Windows payload; it does not modify its DLLs, checkpoint, scientific results or installer.

**Public binary distribution remains pending the specific evidence listed below.** Source-repository preparation and application verification are separate from redistribution entitlement.

## Notices prepared for the existing release

The full [license corpus](docs/licenses/), [dependency inventory](docs/licenses/inventory.json), [binary inventory](docs/licenses/binary-components.json) and [redistribution record](docs/licenses/redistribution-review.json) accompany this review. The Python inventory conservatively includes some environment/build tools; it does not claim all those packages ship. Frontend notices cover the installed runtime dependency closure, including both React versions found locally.

| Components | Retained materials and disposition |
|---|---|
| React, React DOM, xyflow, Three.js, Zustand, Tailwind CSS | Complete MIT copyright/permission texts; added to the mandatory release attachment |
| D3 dependencies | Corresponding ISC/BSD copyright, conditions and disclaimers |
| Python, NumPy, PyTorch, Matplotlib, Pillow and API/support packages | Full locally supplied distribution licenses and bundled third-party notices; not just package metadata |
| PyInstaller | GPL bootloader exception retained; it permits application bundling without making NeuralHeat GPL solely because it was frozen |
| OpenSSL 3.0.16 | Explicit component attribution, complete Apache-2.0 and upstream author list added |
| certifi 2026.4.22 | Full MPL-2.0 and matching editable Python/CA source supplied; source archive checked after creation |
| Microsoft.Web.WebView2 SDK 1.0.3856.49 | Exact NuGet package license verified as BSD-style and retained in full |
| NVIDIA CUDA/cuDNN | Archived CUDA 12.8.1 agreement with supplements and all third-party attachment notices; exact cuDNN 9.19.0 agreement and acknowledgements retained |

The full files are in [vendor notices](docs/licenses/vendor/). The exact WebView2 SDK [license](https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.3856.49/License) permits binary redistribution with its attribution, conditions and disclaimer. It is distinct from the Evergreen browser runtime, which is **not bundled**.

For OpenSSL, the upstream [3.0.16 license](https://github.com/openssl/openssl/blob/openssl-3.0.16/LICENSE.txt) and [copyright](https://github.com/openssl/openssl/blob/openssl-3.0.16/README.md#copyright) identify the Apache-2.0 terms and authors. The new attribution is labeled as NeuralHeat's component identification, not an invented upstream NOTICE.

certifi's public CA data was byte-compared with the frozen payload. Its matching build-environment Python sources and CA bundle are under [covered source](docs/licenses/covered-source/certifi-2026.4.22/). The CA file is stored as `cacert.pem.txt` in Git to distinguish it from ignored private credential files; the release source ZIP restores its proper filename. Source provenance, file hashes and archive verification are in the dependency inventory. This supplies the covered source directly rather than relying on an unspecified future upstream download.

## Deliver these materials with the installer

The original build includes Python notices but omits the frontend license texts. That omission is addressed in the **accompanying distribution materials**, preserving the verified installer unchanged:

```text
NeuralHeat-Studio-Setup.exe
NeuralHeat-Studio-Third-Party-Notices.txt
NeuralHeat-Studio-Certifi-2026.4.22-Source.zip
SHA256SUMS.txt
```

The added files are prepared under `dist/release-support/`. The complete notice attachment includes open-source licenses, NVIDIA agreements/notices, Microsoft SDK attribution, source availability information and [binary distribution terms](docs/licenses/BINARY_DISTRIBUTION_TERMS.txt). Publish and deliver them as one release set, and keep them with offline copies. An installer-only mirror would omit the added materials. A later installer can place them inside the install directory, with separate packaging verification.

The notice/source attachments are not another application ZIP and do not change the verified EXE. Checksums identify each release asset; no upload has occurred.

## NVIDIA review

The [CUDA 12.8.1 archived agreement](https://docs.nvidia.com/cuda/archive/12.8.1/eula/index.html), Attachment A, identifies runtime, BLAS/Lt, FFT/w, random, sparse, solver, runtime-compilation/builtins, JIT-link and NVTX families, allowing version/architecture filename variants. The [cuDNN 9.19.0 supplement](https://docs.nvidia.com/deeplearning/cudnn/backend/v9.19.0/reference/eula.html) expressly identifies runtime DLLs as distributable. Their grants remain conditional on the application distribution requirements.

NeuralHeat adds substantial simulation and scientific inspection functionality. The accompanying terms limit proprietary runtime access/distribution to the application and preserve vendor restrictions, notices and ownership; those restrictions do not relicense NeuralHeat's MIT source. CUDA code targets NVIDIA GPUs, with an independent CPU path.

**Specific unresolved mapping:** `cusolverMg11.dll` is bundled. The generic CUDA Attachment A names `cusolver.dll`, but does not explicitly name the Mg variant. Do not infer that an arbitrary filename variation is a redistribution grant. Retain the matching cuSOLVER package license/redistribution evidence, or obtain NVIDIA's confirmation for that component, before closing this item. No DLL was removed to avoid the question.

The official [CUDA 12.8.1 redistribution manifest](https://developer.download.nvidia.com/compute/cuda/redist/redistrib_12.8.1.json) identifies cuSOLVER 11.7.3.90 and points to its [component license](https://developer.download.nvidia.com/compute/cuda/redist/libcusolver/LICENSE.txt). That component document was also checked: its Attachment A still lists `cusolver.dll` without naming Mg. The manifest provides package provenance; it does not resolve that specific grant ambiguity by itself.

## Microsoft Visual C++ review

Read-only machine inspection on 22 October 2026 found **Visual Studio Code and VC++ Redistributables**, but no registered Visual Studio IDE or Build Tools installation. Standard Visual Studio setup registry keys, `vswhere.exe`, ProgramData instance records and standard install directories were absent. This does not rule out a valid licensed copy on another machine; it does mean the local runtime installation establishes no such entitlement.

All four discovered MSVC runtime DLLs have **valid Microsoft Authenticode signatures**. Full filenames, original filenames, versions, hashes and signature results are in [msvc-binaries.json](docs/licenses/msvc-binaries.json).

| Bundled file | Version | Verification |
|---|---|---|
| `_internal/msvcp140.dll` | 14.51.36247.0 | Original filename matches; Microsoft signature valid |
| `_internal/vcruntime140.dll` | 14.51.36247.0 | Original filename matches; Microsoft signature valid |
| `_internal/vcruntime140_1.dll` | 14.51.36247.0 | Original filename matches; Microsoft signature valid |
| `_internal/numpy.libs/msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll` | 14.40.33810.0 | Original filename is `msvcp140.dll`; Microsoft signature valid; suffix matches content hash |

The [Visual Studio 2026 REDIST list](https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution) permits unmodified files beneath a licensed copy's `VC/redist` tree, excluding the debug directories. It is a directory-based grant, not a public filename/version whitelist. These are release CRT file identities, not debug CRT names, and their valid signatures support byte integrity. Without a licensed reference copy, the inspection cannot prove exact correspondence to its permitted directory. The NumPy file also has an older runtime version and a renamed filename; retain its wheel/runtime provenance and applicable grant rather than treating the 2026 list as proof of every copied version.

Microsoft's [redistribution guidance](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files) limits distribution to licensed Visual Studio users. Its [Community usage guidance](https://visualstudio.microsoft.com/vs/community/) permits individual developers to create their own free or paid applications. The maintainer's stated independent, personal MIT project fits that individual-use description; **eligibility does not establish acquisition or acceptance of a license**.

The supplied [license directory](https://visualstudio.microsoft.com/license-terms/) and [Community 2026 terms page](https://visualstudio.microsoft.com/license-terms/vs2026-ga-community/) identify the official sources. The terms page embeds a DOCX which this executor could not retrieve for a full clause review. Providing a URL is not evidence that those terms were accepted.

To close this item, provide the **actual licensed edition/version, license acceptance/acquisition confirmation and its applicable terms** (a local saved terms file is sufficient for review; no account credentials or product keys). Identify the licensed runtime source/REDIST grant covering the four DLLs, including the older NumPy copy. If the licensed copy is on another machine, identify that fact. Installing/accepting an eligible Community or Build Tools license is a publisher action; this review has not done so on the maintainer's behalf.

## Outcome and reproduction

Frontend, exact WebView2 SDK, OpenSSL attribution, certifi source delivery and retained NVIDIA notice gaps now have concrete accompanying materials. **Do not declare the standalone installer publicly cleared yet:** MSVC entitlement/provenance and the cuSOLVER Mg redistribution mapping still require evidence, and the added notices/source must accompany every binary distribution.

Inno Setup and Node.js are build tools, not separately installed application runtimes. Their build-tool terms do not replace bundled-component obligations. All original application and scientific assets remain preserved.

Recreate the additive attachments without rebuilding the application:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_release_notices.py
```

The manifest's `binary_publication_ready` stays false while the recorded outstanding items remain. Source audit success is not binary license clearance.
