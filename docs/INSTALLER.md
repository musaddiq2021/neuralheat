# NeuralHeat Studio Windows installer

The Inno Setup installer wraps an **existing verified PyInstaller onedir release**. It never retrains the CNN, rebuilds the frontend, changes PyTorch, or removes CUDA libraries. The portable folder and its scientific assets are read only inputs.

## End-user installation

Run **NeuralHeat-Studio-Setup.exe** and accept the Windows elevation prompt. The default location is `C:\Program Files\NeuralHeat Studio`. Setup provides a Start Menu shortcut, an optional desktop shortcut (unchecked initially), a license page, an installation summary and a launch option. The wizard uses the application icon and scientific workstation identity. Dark mode is used with Inno Setup 6.6+; older supported compilers use the standard modern wizard.

Only the shortcuts are needed for normal use. The complete `_internal` directory stays in the application directory. Never move or remove individual DLLs. Windows Settings > Apps / Control Panel > Programs and Features provides the normal uninstall entry. Uninstalling removes installed application files and shortcuts while preserving personal experiments, settings and logs.

The application, checkpoint, matching cached data, solver, reports, UI and PyTorch CPU/CUDA dependencies are included. There are no installation or application downloads, CDN dependencies, Python or Node.js prerequisites. The CPU path works without an NVIDIA GPU; CUDA requires a compatible NVIDIA driver. The CUDA Toolkit is unnecessary. Windows 10 1809+ / Windows 11 x64 and the .NET Framework included with supported Windows installations are required.

**WebView2:** By default Microsoft Edge WebView2 Evergreen Runtime must already be installed. Setup checks for it before copying application files and gives an actionable message if missing. This variant is offline capable on machines with that prerequisite; it does not bundle the browser runtime. For an installer that also supplies WebView2 on an offline machine, pass the full signed x64 Evergreen Standalone Installer to the build command below. The small online bootstrapper is rejected. The bundled runtime runs only when WebView2 is missing. GPU drivers remain a system prerequisite in either variant.

Writable state remains `%LOCALAPPDATA%\NeuralHeat Studio\`, including `runs`, `logs`, `cache`, `settings` and the WebView2 profile. Setup does not grant write permissions to Program Files and never removes AppData on uninstall. Training writes new run directories and keeps the bundled CNN unchanged. The application starts its loopback backend on an available port and stops it when the window closes.

## Reproducible build

Install [Inno Setup 6.3+ or 7](https://jrsoftware.org/isdl.php) on the developer machine. The script locates `ISCC.exe` on PATH, under Program Files, or under `%LOCALAPPDATA%\Programs\Inno Setup 7` / `Inno Setup 6`. The existing developer `.venv` supplies Python and Pillow for asset generation and verification; these build tools are not required on end-user machines.

```powershell
cd D:\neuralheat

# Use dist/desktop/latest.json and its passing frozen release reports.
# Compile, then actually install and test the installed EXE.
.\scripts\build_installer.ps1

# Optional: include Microsoft's full signed offline WebView2 runtime installer.
.\scripts\build_installer.ps1 -WebView2Installer 'D:\Downloads\MicrosoftEdgeWebView2RuntimeInstallerX64.exe'

# A nonstandard compiler or a compile-only run:
.\scripts\build_installer.ps1 -Compiler 'C:\Tools\Inno Setup 7\ISCC.exe' -BuildOnly
```

No downloads or tool reinstalls occur in these scripts. If selecting a different existing portable build, provide both `-SourceExecutable` and `-SourceVerificationDirectory`. It must have passing CPU and full frozen release tests. LZMA2 solid compression includes every source file; one block compressor and a 64 MiB dictionary limit memory use. Compression of this CUDA build can take tens of minutes. The output is a single full setup EXE, not a self-extracting ZIP or a bootstrapper.

Outputs:

```text
dist/installer/<build-id>/NeuralHeat-Studio-Setup.exe
dist/installer/<build-id>/NeuralHeat-Studio-Setup.exe.sha256
reports/installer/<build-id>/candidate.json
reports/installer/<build-id>/compile.log
reports/installer/<build-id>/bundle-audit.json
reports/installer/<build-id>/installation-<test-id>/installer.json
reports/installer/<build-id>/installation-<test-id>/installer.md
```

`reports/installer/candidate.json` points to the most recent built candidate. A successful compiler run is recorded as **built_not_install_verified**; it is not proof of an installed application test. The application version is read from the source EXE. Reports retain the compiler hash, installer script hash, checkpoint hash, all 2,799 source file hashes, compressed size and test evidence. Existing releases are never replaced.

## Actual installation verification

```powershell
# Resume testing a compiled candidate without recompiling or rebuilding anything:
.\scripts\test_installer.ps1

# Verify a real Program Files installation, desktop shortcut and uninstall cycle.
# Run from an elevated Windows PowerShell on an interactive desktop:
.\scripts\test_installer.ps1 -AllUsers -TestDesktopShortcut -TestUninstall
```

The default test performs a real per-user Inno installation in a fresh isolated directory under `.cache/installer-tests/`, with the standard NeuralHeat Studio Start Menu group. The `-AllUsers` test exercises the normal Program Files destination and machine-wide registration. Both refuse to replace an existing NeuralHeat installation or overwrite an existing Start Menu or desktop shortcut. The default leaves the test installation available for inspection; `-TestUninstall` removes it through its actual uninstaller and checks that personal data survives. Use the uninstall entry before running another install test.

The installed EXE runs with Python/Node removed from PATH, unrelated working directory, blocked HTTP(S) proxies and isolated `LOCALAPPDATA`. No custom `--user-data-dir` is supplied: the test checks that the application's normal AppData discovery is used. Proxy blocking is not firewall isolation. Tests verify:

- Actual Setup execution, uninstall registry entry and shortcut target.
- All installed application files against the original source hashes, permitting only Inno's generated `unins000.*` files.
- CPU inference, numerical solver agreement, fixed checkpoint, saved reports, real activations and idle launch.
- Automatic CUDA selection on this CUDA test host, smoke training, cancellation and backend shutdown.
- Actual WebView2 Physics, Network Explorer, Training and Latency pages, plus resizing.
- Application files remain unchanged after execution and the original portable build is preserved.
- With `-TestUninstall`, removal of the application, shortcut and uninstall entry, while a personal data marker survives.

Failed or missing checks produce **unverified**, preserve their logs and fail the command. Restricted executors can prevent HKCU registration, shortcuts, elevation or WebView2 controller creation; do not label such a run verified. Resume from normal Windows PowerShell using the same candidate. No recompilation is needed.

## Release considerations

The project does not currently include a code-signing certificate. The EXE is unsigned and Windows SmartScreen may show an unrecognized publisher warning. Production distribution should sign the application and installer with your own trusted certificate and retest the final signed artifact. Do not distribute the compiler or imply its license covers the application. The project's MIT license and existing third-party notices are included in the installed folder.

Microsoft documents the WebView2 detection registry keys and offline deployment procedure in its [runtime distribution guide](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution). Compression settings follow [Inno Setup's LZMA2 documentation](https://jrsoftware.org/ishelp/topic_setup_compression.htm).

## Recorded installer build

Inno Setup **7.1.0**, detected under `%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe`, compiled the existing verified `20261021-184035-046` portable release without rebuilding the scientific application.

| Measurement | Value |
|---|---|
| Setup EXE | `D:\neuralheat\dist\installer\20261022-102027-253\NeuralHeat-Studio-Setup.exe` |
| Compressed bytes | 1,863,668,204 |
| Decimal GB / binary GiB | 1.863668 GB / 1.735676 GiB |
| Complete source payload | 2,799 files / 4,493,565,290 bytes |
| Compression time | 1,948.77 seconds |
| Installer SHA256 | `861038b7f183f936db1a545d20d148c113fc31c00ae62ba1a00a043a0b8e64a9` |
| WebView2 | Required preinstalled; not bundled in this artifact |

All source hashes matched the earlier portable-release inventory and remained unchanged after compilation. The current installation verification status is recorded separately in `reports/installer/latest.json` and the referenced `installer.json`; compilation alone does not mark this build verified. An installation attempted inside the restricted executor decompressed the application but was denied Start Menu and uninstall-registry writes (Windows error 5), and Inno Setup rolled it back. Normal Windows PowerShell is required to complete those system integration checks.
