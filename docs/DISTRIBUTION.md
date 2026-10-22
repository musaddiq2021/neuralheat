# Portable GitHub distribution

Release packaging is separate from building the Windows executable. `scripts/package_distribution.ps1` reads an existing verified onedir release and creates a new archive and extraction directory. It does not alter or rebuild that application.

## Size audit

The audited reference release contains 2,799 files totaling **4,493,565,290 bytes (4.185 GiB)**. The existing Deflate ZIP is **2,886,201,713 bytes (2.688 GiB)**.

The measured LZMA2 candidate is **1,904,214,072 bytes (1.773 GiB)**: **34.02% smaller** than that ZIP, with every extracted file matching the original. Its installed size is unchanged. The extracted executable passed CPU/CUDA scientific checks, smoke training, cancellation and backend shutdown in the executor. Native WebView2 initialization failed in this executor for both the untouched original and the extracted app; full UI verification must be completed using `scripts/test_distribution.ps1` in an interactive Windows session. The latest `reports/distribution/20261021-195626/distribution.json` records the exact verification status rather than treating partial checks as complete.

| Largest library | Uncompressed MiB |
|---|---:|
| `torch_cuda.dll` | 773.96 |
| `cublasLt64_12.dll` | 643.41 |
| `cudnn_engines_precompiled64_9.dll` | 458.73 |
| `cusparse64_12.dll` | 361.95 |
| `cufft64_11.dll` | 263.33 |
| `cudnn_adv64_9.dll` | 256.55 |
| `torch_cpu.dll` | 253.65 |

`_internal/torch` accounts for about 95% of the full folder. Exact duplicates total only 680,292 redundant bytes (0.65 MiB), mostly license texts. The similarly named `nvrtc64_120_0.dll` and `nvrtc64_120_0.alt.dll` have different hashes; they are not interchangeable duplicates.

The executable's embedded Python archive includes `_pytest` and PyTorch internal test modules pulled in by the standard torch hook. Those test modules occupy about 2 MiB compressed inside the executable; matching test-source files occupy only a few MiB outside it. They are potential exclusions for a future separately tested PyInstaller build, with negligible effect on this release's size. They are retained in the compression-only candidate.

TorchVision, TorchAudio, SciPy, pandas, Jupyter, notebook, pip and PyInstaller are absent from the embedded runtime. The existing spec already excludes Qt variants, CEF, GTK, Tk, IPython and the top-level pytest module, and restricts Matplotlib to Agg. Do not exclude `sympy`, `unittest`, Torch source files, or CUDA libraries simply because application code does not import them directly: PyTorch imports dependencies internally and uses Python source inspection. Removing its source collection can also break FX, inspection, or error handling.

No modules, scientific files or DLLs are removed by this packaging workflow. A fresh build with a different PyTorch/CUDA wheel could have a different size, but also requires renewed numerical and runtime validation. This workflow retains the known working runtime.

Detailed audit evidence is in `reports/distribution/audit/bundle-audit.json`, `bundle-files.csv`, `embedded-modules.json` and `zip-inventory.json`.

## Compression and reproduction

The default archive is a standard **`.tar.xz` using LZMA2**, readable by 7-Zip and Windows' built-in `tar.exe`. XZ supports multithreaded encoding in libarchive; its memory-bounded default here is two threads at level 8. Stronger settings can take substantially more RAM and time, without necessarily changing whether the archive meets the size target.

```powershell
cd D:\neuralheat
.\scripts\package_distribution.ps1
# Optional stronger compression when memory permits:
.\scripts\package_distribution.ps1 -Threads 2 -CompressionLevel 9
```

For a solid `.7z` container, install 7-Zip or provide its executable path:

```powershell
.\scripts\package_distribution.ps1 -Format SevenZip -SevenZip 'C:\Program Files\7-Zip\7z.exe'
```

The 7-Zip path uses LZMA2, ultra compression, a 64 MiB dictionary and solid mode. Without 7-Zip, the script can use Windows libarchive's 7z writer, which uses a single LZMA2 encoder and can be much slower. Its `threads` option does not parallelize that encoder. LZMA2 changes only the archive representation; after extraction the application files and inference behavior remain the same.

Each run creates `dist/distribution/<run-id>/` and `reports/distribution/<run-id>/`, retains a SHA256 manifest of the original release, extracts into a new folder, checks every file, and executes the frozen CPU and WebView2/CUDA/worker release tests from that extracted folder. It then hashes the original folder again and measures both compressed and extracted sizes. It only reports success when these checks pass **and** the archive is strictly below 1.9 GiB. The original ZIP and working onedir release are retained.

To repeat the runtime verification of the latest extracted candidate without recompressing it, run `scripts/test_distribution.ps1`. Use an ordinary interactive Windows PowerShell session with WebView2 and CUDA available. The script records failed or missing checks rather than treating CPU fallback as proof of CUDA preservation. A headless backend test alone is insufficient to mark the complete desktop release verified.

The result includes the archive, a `.sha256` checksum file and a JSON report. The extracted test directory is for verification; upload only the archive and checksum to GitHub, not that whole directory. The unpacked application remains about 4.185 GiB; stronger compression reduces download size rather than installed size. End users need free space for the archive and extracted application.

## Extract and launch

Use 7-Zip's Extract operation, or built-in Windows PowerShell:

```powershell
New-Item -ItemType Directory -Path .\NeuralHeat-Portable
tar.exe -xf .\NeuralHeat-Studio-Windows-CUDA.tar.xz -C .\NeuralHeat-Portable
& '.\NeuralHeat-Portable\NeuralHeat Studio\NeuralHeat Studio.exe'
```

Keep `_internal` beside the exe. End users still need WebView2 and a compatible NVIDIA driver for CUDA; Python, npm and the CUDA Toolkit are unnecessary. Extraction does not download any dependencies.

[GitHub requires each individual Release asset to be under 2 GiB](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases). The 1.9 GiB target leaves a margin below that bound. Generated reports use exact byte counts and binary GiB throughout; neither a renamed oversized ZIP nor split volumes count as a single archive meeting that target.
