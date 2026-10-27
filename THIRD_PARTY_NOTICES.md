# Third-party notices and redistribution review

NeuralHeat's own source is [MIT licensed](LICENSE). Dependencies retain their licenses. This review covers the verified Mg-free beta, with unchanged scientific assets. The original DLLs, checkpoint, scientific results and older installer remain preserved.

**The redistribution review and actual Windows installation verification are complete for v1.0.0-beta.1.** The release omits cuSOLVERMg, retains the documented Microsoft/NVIDIA conditions, and includes complete notices and covered source. See the [verified beta record](docs/verification/windows-beta.json). This does not clear the preserved older retained-Mg installer as a different payload.

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

The original installer remains unchanged. The new beta includes complete upstream notices, certifi covered source and protective installation terms inside the installed application. Also deliver these accompanying release materials:

```text
NeuralHeat-Studio-Setup.exe
NeuralHeat-Studio-Third-Party-Notices.txt
NeuralHeat-Studio-Certifi-2026.4.22-Source.zip
SHA256SUMS.txt
```

The added files are prepared under `dist/release-support/`. The complete notice attachment includes open-source licenses, NVIDIA agreements/notices, Microsoft SDK attribution, source availability information and [binary distribution terms](docs/licenses/BINARY_DISTRIBUTION_TERMS.txt). Publish and deliver them as one release set, and keep them with offline copies. An installer-only mirror would omit the added materials. A later installer can place them inside the install directory, with separate packaging verification.

The notice/source attachments are not another application ZIP and do not change the verified EXE. Checksums identify each release asset; no upload has occurred.

## NVIDIA review and practical resolution

The original payload's actual file is **`cusolverMg64_11.dll`** (157,071,360 bytes). The earlier shortened name `cusolverMg11.dll` was incorrect. Its original location is `dist/desktop/20261021-184035-046/NeuralHeat Studio/_internal/torch/lib/`. The original PyInstaller TOC traces it to the matching PyTorch 2.11.0+cu128 wheel file; packaged bytes, source bytes and wheel RECORD all match.

The [CUDA 12.8.1 agreement](https://docs.nvidia.com/cuda/archive/12.8.1/eula/index.html) and [exact cuSOLVER component license](https://developer.download.nvidia.com/compute/cuda/redist/libcusolver/LICENSE.txt) were checked. The [official manifest](https://developer.download.nvidia.com/compute/cuda/redist/redistrib_12.8.1.json) identifies cuSOLVER 11.7.3.90. Both reviewed lists name ordinary `cusolver.dll`, without explicitly naming Mg; ordinary-family membership is not treated here as an express Mg grant. The complete component license is now retained separately in the vendor notices.

**Removal route investigated and implemented experimentally:** none of the 111 inspected PE files imports Mg, and NeuralHeat does not call the multi-GPU solver. PyTorch ordinarily eagerly loads every DLL in its Windows library directory; a real probe confirmed Mg is loaded at import in the original environment. A controlled exclusion copy and a fresh guarded PyInstaller build both run without it, preserving ordinary cuSOLVER and all other CUDA components.

Both candidates passed frozen CPU/CUDA inference, solver comparison, real activations, smoke training, cancellation and benchmark generation. PSAPI confirmed no Mg DLL or original/venv fallback. Earlier restricted WebView2 failures remain historical evidence. On 27 October the actual new Program Files installation passed all four native pages, resize, CPU/CUDA/worker, shortcuts, AppData and uninstall tests. The equivalent guarded exclusion is now adopted in production packaging; the original build remains intact.

The [experiment record](docs/CUSOLVERMG_EXPERIMENT.md) and [public summary](docs/licenses/cusolvermg-experiment.json) preserve both historical failures and the final installed verification. This release contains no Mg component, so no grant for that omitted file or vendor enquiry is needed. The [unsent enquiry](docs/NVIDIA_LICENSING_ENQUIRY.md) remains only a fallback for a different payload that retains it.

The retained [cuDNN 9.19.0 supplement](https://docs.nvidia.com/deeplearning/cudnn/backend/v9.19.0/reference/eula.html) explicitly identifies runtime DLLs as distributable, subject to its conditions. Existing NVIDIA agreements/notices and the accompanying application terms continue to apply to the libraries still shipped.

## Microsoft Visual C++ review

**Resolved for this unchanged runtime payload, 27 October 2026.** Visual Studio Community 2026 18.11.1 is installed with the C++ desktop workload. The publisher confirmed accepting its terms. The complete [official Community DOCX](docs/licenses/vendor/Microsoft-Visual-Studio-Community-2026.docx) and [readable text](docs/licenses/vendor/Microsoft-Visual-Studio-Community-2026.txt) are archived and reviewed; no repeat acceptance is needed.

The three root 14.51.36247.0 CRT DLLs exactly match the installed licensed release CRT directory. NumPy's 14.40.33810.0 DLL now also has an exact SHA256 match to object code extracted from the official signed Microsoft runtime installer identified in Microsoft's manifest. Its existing hash-renamed file and NumPy imports remain unchanged.

| Bundled file | Version | Official provenance |
|---|---|---|
| `_internal/msvcp140.dll` | 14.51.36247.0 | Exact installed licensed CRT match |
| `_internal/vcruntime140.dll` | 14.51.36247.0 | Exact installed licensed CRT match |
| `_internal/vcruntime140_1.dll` | 14.51.36247.0 | Exact installed licensed CRT match |
| `_internal/numpy.libs/msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll` | 14.40.33810.0 | Exact official runtime-package match |

The accepted Community **Distributable Code** grant and [2026 REDIST separately downloaded runtime provision](https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution#visual-c-runtime-files) are the redistribution basis for this licensed publisher. The [runtime EULA](docs/licenses/vendor/Microsoft-Visual-Cpp-Runtime-14.40-ENU.txt) is retained but is not treated as an independent redistribution grant. The older file is not falsely described as a match in the installed 14.51 tree.

NeuralHeat supplies significant primary functionality. Distribute these files unmodified, retain their notices and protective downstream terms, avoid debug/preview components and conflicting source-disclosure licensing, and observe the accepted publisher indemnity and applicable trade conditions. Setup presents MIT plus the [binary conditions](docs/licenses/BINARY_DISTRIBUTION_TERMS.txt), and complete upstream notices accompany the app. Users need no Visual Studio installation merely to run NeuralHeat.

See [MSVC documentation](docs/MSVC_REDISTRIBUTION.md) and [exact provenance](docs/licenses/msvc-provenance.json) for official URLs, document hashes, installed edition, signature results, extracted-file comparisons and continuing conditions. The original TOCs still correctly record the historical System32/wheel collection paths. No proprietary DLL was added to Git, replaced, renamed or removed to obtain this result. No additional Community installation or vendor permission letter is required for this documented route.

## Outcome and reproduction

Frontend, exact WebView2 SDK, OpenSSL, certifi, NVIDIA and Microsoft materials are complete. **The MSVC review and normal-Windows installation/desktop validation are resolved.** Complete notices/source are included in the verified installer and accompanying release assets and must remain with redistribution. The installed notice bundle contains stable upstream conditions rather than transient release-test status.

Inno Setup and Node.js are build tools, not separately installed application runtimes. Their build-tool terms do not replace bundled-component obligations. All original application and scientific assets remain preserved.

Recreate the additive attachments without rebuilding the application:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_release_notices.py
```

The manifest's `binary_publication_ready` stays false while the recorded outstanding items remain. Source audit success is not binary license clearance.
