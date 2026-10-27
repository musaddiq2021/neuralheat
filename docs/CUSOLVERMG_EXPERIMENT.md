# cuSOLVERMg exclusion: measured investigation and release procedure

Status: **resolved, 27 October 2026**. The Mg-free installer passed actual Program Files installation, CPU/CUDA/worker, all native pages/resize, shortcuts, AppData and uninstall verification. The [public installed record](verification/windows-beta.json) and [experiment summary](licenses/cusolvermg-experiment.json) retain the evidence. The equivalent guarded policy is adopted in production packaging. Original builds and historical failed restricted tests remain preserved. No Mg grant or vendor enquiry is needed for this Mg-free release.

## What was actually found

The exact filename is **`cusolverMg64_11.dll`**, not the shortened `cusolverMg11.dll` used in the earlier notice. In the original portable release it is located at:

```text
D:\neuralheat\dist\desktop\20261021-184035-046\NeuralHeat Studio\_internal\torch\lib\cusolverMg64_11.dll
```

It is 157,071,360 bytes, SHA256 `c3377f10606ff0606be2f08401d54aff6c37f137b78d6b6e21be356a5b4d6cc2`. The original PyInstaller `Analysis-00.toc` and `COLLECT-00.toc` trace it to `.venv\Lib\site-packages\torch\lib\cusolverMg64_11.dll`. Both source and frozen hashes match the installed PyTorch 2.11.0+cu128 wheel's RECORD.

The production spec explicitly calls `collect_dynamic_libs("torch")`; the installed PyInstaller torch hook also collects dynamic libraries. This is broad dependency collection, not evidence that NeuralHeat calls a multi-GPU solver. The original PyTorch Windows `_load_dll_libraries()` globs every DLL in `torch/lib` and calls LoadLibrary. A real import probe confirmed Mg is loaded during ordinary `import torch` in the original environment. Thus **loaded at startup** and **needed by NeuralHeat's operations** are different findings.

Static PE inspection covered **111 EXE/DLL/PYD files**, including ordinary and delay-load imports, with no parse failures. None imports cuSOLVERMg. `torch_cuda.dll` does import ordinary `cusolver64_11.dll`, which is retained. A source search found no NeuralHeat calls to cuSOLVERMg or multi-GPU eigensolvers; its CNN uses convolutions, pooling, interpolation and an Adam training path. PE inspection cannot rule out all dynamic loading, so it was followed by frozen runtime tests.

## Component license review

The official [CUDA 12.8.1 manifest](https://developer.download.nvidia.com/compute/cuda/redist/redistrib_12.8.1.json) identifies cuSOLVER **11.7.3.90** and points to the [component-specific license](https://developer.download.nvidia.com/compute/cuda/redist/libcusolver/LICENSE.txt). The actual ordinary library's `cusolverGetProperty` reports **11.7.3**. The complete component license is retained at [NVIDIA-libcusolver-component-LICENSE.txt](licenses/vendor/NVIDIA-libcusolver-component-LICENSE.txt), separately from the general 12.8.1 agreement; it states an upstream update date of 12 January 2024.

Both reviewed Attachment A lists name `cusolver.dll`, not the Mg DLL. The [12.8 API documentation](https://docs.nvidia.com/cuda/archive/12.8.1/cusolver/index.html) distinguishes the Mg API. This review therefore does not equate ordinary cuSOLVER's listed name with an express Mg grant. It also does not claim NVIDIA prohibits redistribution: the unresolved question is which grant covers this exact component. No support message has been sent.

## Separate payloads created

1. **Controlled exclusion copy:** `dist/experiments/20261022-114145-389073/NeuralHeat Studio`. Its **2,798 retained files were individually SHA256-compared with the original**, with exactly one omitted file: cuSOLVERMg. No source file was deleted. The frozen EXE itself is unchanged. The resulting tree is **4,336,493,930 bytes**; the reduction is exactly **157,071,360 bytes** (149.795 MiB). This is an isolated packaging experiment, not a newly compiled app.
2. **Fresh PyInstaller build:** `dist/experiments/no-cusolvermg-20261022-125001-723/NeuralHeat Studio`. The experimental spec executes the production recipe with an isolated collection policy. It requires the known torch version, excludes exactly the Mg filename after dependency analysis, rejects unexpected data copies, and refuses to collect if any retained PE imports the omitted DLL. All remaining CUDA libraries are preserved. The build log records successful EXE and COLLECT stages. An initial PowerShell wrapper lost its native exit code after waiting; the completed artifacts were resumed, independently tested, and the wrapper was corrected to use Python subprocess exit handling. This was not a PyInstaller compilation failure.

Neither experiment changes `dist/desktop/latest.json`, the original portable tree or the original installer. After actual installer verification, the equivalent collection policy was explicitly adopted in [freeze_policy.py](../desktop/freeze_policy.py) and the production recipe. The [historical adapter](../desktop/experiments/no-cusolvermg.spec) now reuses that shared policy rather than applying a second filter.

## Executed verification

The controlled exclusion and fresh PyInstaller candidates each passed frozen CPU and CUDA backend tests:

- Python/PyTorch startup; explicit CUDA selection on the RTX 4070 Laptop GPU; CPU fallback.
- Loading the original CNN checkpoint and real inference/activation inspection; graph structure and saved reports.
- Physics Lab simulation API and bitwise agreement with the numerical solver; trained-final-time prediction.
- Smoke training, safe cancellation and benchmark generation for the actual CPU/CUDA methods.
- Four isolated smoke runs in total completed three epochs each with recorded training device `cuda`; each generated all five solver/CPU/CUDA forward/end-to-end benchmark method groups. These runs are not replacements for the saved reference experiment.
- Verification of all **68 bundled scientific assets**, and internal backend shutdown.

The test runner enumerated each child process's mapped DLLs through Windows PSAPI. It observed the candidate's own CUDA libraries, **no cuSOLVERMg**, and no fallback to the original payload or `.venv`. This is stronger than merely observing that the excluded file is absent from a directory. These are smoke/functionality experiments; the historical accuracy and benchmark results have not been rewritten as new measurements.

The WebView2 test attempted the actual interface. In this restricted session it failed to create its controller with HRESULT **0x8000FFFF**, followed by `Main window failed to start`. An **unchanged original-release control** produced the same controller/window failure while its CUDA backend passed. This supports an execution-environment limitation, but does not replace successful normal-Windows UI verification. No four-page UI pass or installed-candidate pass is claimed here.

Local raw evidence is under `reports/redistribution/20261022-114145-389073/` and `reports/redistribution/no-cusolvermg-20261022-125001-723/`. A small [public summary](licenses/cusolvermg-experiment.json) omits private process logs and transient session details.

### Fresh beta verification, 27 October

The same freshly frozen candidate was retested under `reports/redistribution/release-beta-20261027-090635-937/runtime`. Frozen CPU and CUDA/worker checks passed again, with the unchanged checkpoint, all 68 packaged scientific assets, real simulation/inference/activations, smoke training, cancellation, and benchmark generation in isolated user data. No Mg DLL or original/venv fallback was observed. The real WebView2 attempt again failed to create its controller (`0x8000FFFF`, `Main window failed to start`); this remains an unverified desktop check, not an application-feature regression established by the test.

Run `scripts/verify_beta_desktop.ps1` from normal Windows PowerShell for the real desktop evidence. It tests the existing candidate without rebuilding or installing it and writes `verified-candidate.json` only when all three frozen checks pass. `finish_cusolvermg_candidate.ps1 -RuntimeVerificationDirectory <that-runtime-directory>` can reuse this matching executable-hash-bound evidence, avoiding another unnecessary smoke run. Installer compilation is conditional on the completed MSVC review. `-BuildOnly` stops after compilation so an installed-application test can run separately in normal Windows.

## Finish the actual desktop checks

From normal Windows PowerShell, test the **freshly frozen** candidate and then compile/install its separate installer only if all runtime checks pass:

```powershell
cd D:\neuralheat
.\scripts\finish_cusolvermg_candidate.ps1 `
  -Executable '.\dist\experiments\no-cusolvermg-20261022-125001-723\NeuralHeat Studio\NeuralHeat Studio.exe'

# For the complete Program Files install test, use elevated PowerShell and add:
# -AllUsers
```

The script tests CPU, CUDA, workers and all four real WebView2 pages, then includes the complete notices and certifi covered source **inside that candidate**, compiles a new timestamped installer, and invokes the existing installation/shortcut/runtime/uninstall tests. It refuses to replace an existing personal installation. It does not publish, accept Microsoft terms, replace the old installer or promote the production recipe. It stops before installer compilation if the real UI tests fail. A Program Files test requires elevation; per-user testing still verifies real Windows installer registration and shortcuts.

Those checks and the MSVC review are now complete for the beta; the guarded exclusion is adopted and the new installer is verified. The original retained-Mg installer stays preserved as a different, non-upload payload. If a future feature requires restoring Mg, review that changed payload's grant rather than applying this omission-based record to it.

## Reproduce the investigation/build

```powershell
.\.venv\Scripts\python.exe scripts/investigate_redistribution.py --create-experiment
.\scripts\build_cusolvermg_candidate.ps1 -BuildOnly
```

Each command creates fresh timestamped directories. Building from the existing production scientific/React assets requires no frontend rebuild or retraining. `test_redistribution_candidate.py` accepts a specific frozen EXE and a fresh report directory; it starts only the allowlisted application self-tests, not arbitrary shell commands.
