# NeuralHeat Studio for Windows

NeuralHeat Studio uses the complete production React interface inside a native, resizable pywebview window rendered by Microsoft WebView2. It starts its own FastAPI engine on an available loopback port and closes it with the window. No external browser, terminal, Node.js, npm, or Python installation is required on the destination machine.

## Running a release

Copy the entire **NeuralHeat Studio** release folder to the machine, including `_internal`. Double-click **NeuralHeat Studio.exe**. A loading screen appears while the saved PyTorch model initializes. The application opens Physics Lab automatically; opening it never trains a model.

System prerequisites are Windows 10/11 x64, the Microsoft Edge WebView2 Evergreen Runtime, and a compatible NVIDIA driver for CUDA acceleration. The packaged CUDA-enabled PyTorch runtime includes its CUDA libraries; installing the CUDA Toolkit is unnecessary. CPU inference remains available when CUDA is unavailable. The desktop host explicitly selects WebView2 and reports an actionable startup error if it is missing; it does not fall back to Internet Explorer.

The application operates locally after installation. All JavaScript, CSS, scientific data, checkpoint weights, and plots are shipped in the folder. There are no CDN fonts or runtime npm/pip downloads. Installing WebView2 on an offline machine requires Microsoft's offline Evergreen installer separately.

The native Workspace menu opens experiment results or logs. The View menu navigates scientific workspaces. The window uses standard Windows controls, keyboard navigation and resizing; its last size is restored. Closing during an experiment asks whether to stop it, then terminates the worker and its process tree. Only one desktop window manages a given user workspace.

## Read-only assets and writable state

The immutable snapshot is `_internal/scientific_assets/`:

| Asset | Purpose |
|---|---|
| `frontend/dist/` | Production Vite application, including React Flow and Three.js chunks |
| `models/best.pt`, `models/training.json` | Existing trained model and matching history |
| `data/<checkpoint-dataset-id>/` | Complete matching float32 training, validation and test cache |
| `configs/` | Approved smoke and full experiment presets |
| `reports/`, `figures/`, archived `runs/` | Existing numerical evidence and saved run histories |
| `asset-manifest.json` | SHA256 checksums of every staged asset |

Writable state goes to `%LOCALAPPDATA%\NeuralHeat Studio\`:

```text
runs/studio/<run-id>/   New experiment checkpoints, data, figures, reports and durable SSE events
logs/                  Rotating desktop logs and startup diagnostics
cache/                 Matplotlib and PyTorch caches
settings/window.json   Last window size
webview/               WebView2 profile and local storage
```

The packaged engine reads the checkpoint once. New experiments write new run directories and never replace the packaged checkpoint. Source project artifacts in `D:\neuralheat` are also never changed by desktop execution. Historical reports are displayed unchanged and retain their original hardware and timing provenance.

Each launch reserves its listening socket directly with port `0`; it does not search for a port and then release it before use. Only `127.0.0.1` is bound. Desktop requests require a random per-launch HttpOnly session cookie, and POST/SSE origins are restricted to that launch's actual origin. This avoids fixed-port collisions and prevents unrelated browser origins from driving the experiment controls.

## Build from source

Build prerequisites apply only to the developer machine: existing `.venv`, 64-bit Python, Node.js 22.12+ or 24 LTS, installed npm dependencies, and CUDA-enabled PyTorch. Use the existing PyTorch installation rather than replacing it with a CPU wheel. The original development launcher and CLI remain available unchanged.

From Windows PowerShell outside the restricted coding sandbox:

```powershell
cd D:\neuralheat
.\.venv\Scripts\python.exe -m pip install -e ".[studio,desktop,dev]"
npm.cmd install
.\scripts\build_desktop.ps1
```

Alternatively, `scripts/build_desktop.ps1 -InstallDependencies` performs both dependency installations first. The normal build checks the existing environment without automatically upgrading it.

The build performs TypeScript, ESLint, frontend regression tests, a production Vite build, Ruff and the full Python test suite. It then copies and hashes scientific assets into a **new** staging directory, runs the checked-in PyInstaller spec in **onedir/windowed** mode, and tests the actual executable. Existing releases and source assets are not deleted or replaced. The command fails unless every required release check succeeds.

Output is versioned by build time:

```text
dist/desktop/<build-id>/NeuralHeat Studio/NeuralHeat Studio.exe
dist/desktop/<build-id>/NeuralHeat Studio/_internal/...
reports/desktop/<build-id>/...
```

`dist/desktop/latest.json` points to the most recent **verified** release. Failed attempts produce `build-failure.json` without claiming a successful executable. Reports retain the Python environment, npm lockfile, asset manifest and frozen verification results. CUDA DLLs make the folder large; distribute the whole directory, typically as a ZIP. The exe has Windows product/version metadata and a multi-resolution application icon. Code signing is a separate release step; this project does not claim to provide a signed installer.

## Packaged verification

The build launches the frozen executable with developer Python/Node paths removed, no source `PYTHONPATH`, an unrelated working directory, and unavailable HTTP(S) proxies. This checks local operation but is not equivalent to firewall-level isolation or testing a fresh Windows VM.

The first pass explicitly requests CPU. The second uses automatic CUDA selection and an actual WebView2 window. Verification checks the checkpoint, all asset hashes, exact agreement with the existing numerical solver, inference, real activations, saved reports/logs, all four scientific workspaces, the graph's 17 nodes, window resizing, a complete smoke experiment through the frozen worker, cancellation of a second worker, and closure of the internal backend port. **These smoke runs are explicit release tests, never an application startup behavior.** New release-test artifacts stay under `.cache/desktop-release-tests/`.

To retest a verified build:

```powershell
.\scripts\test_desktop.ps1
# Or a specific built executable:
.\scripts\test_desktop.ps1 -Executable 'D:\path\NeuralHeat Studio\NeuralHeat Studio.exe'
```

To inspect the source host during development without Vite:

```powershell
npm.cmd run build
.\.venv\Scripts\python.exe -m neuralheat.desktop.main
```

This uses the production build and the existing Python environment. It is not a substitute for frozen release verification.

## Experiment execution and shutdown

Development Studio continues to run `scripts/run_experiment.py` through Python. In a release, an executable cannot act as `python -m ...`; the manager instead launches the **same packaged exe** in an allowlisted worker mode. The worker calls the original dataset, training, evaluation and benchmark functions directly. It does not accept arbitrary commands or import external scripts. Epochs and console lines stream from its durable log into the existing SSE protocol. Per-stage reports and logs preserve the original filenames. The Windows Job Object owns the worker process tree for cancellation and shutdown.

Release tests run before packaging. Experiment workers do not run pytest on the end user's machine. Numerical methods, normalization, model architecture, training defaults and benchmark definitions remain those of the existing scientific modules. The CNN still predicts only its trained final time; numerical animation never presents intermediate CNN predictions.

## References

- [pywebview Windows rendering requirements](https://pywebview.flowrl.com/guide/web_engine)
- [pywebview freezing guidance](https://pywebview.flowrl.com/guide/freezing)
- [PyInstaller spec and onedir packaging](https://pyinstaller.org/en/stable/spec-files.html)
- [Microsoft WebView2 distribution](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)
