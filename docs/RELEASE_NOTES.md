# NeuralHeat Studio v1.0.0-beta.1 — Windows prerelease

A Windows scientific computing workstation for 2D heat diffusion and PyTorch surrogate inspection.

- Physics Lab: synchronized initial/reference/CNN/error fields, numerical time animation, source placement and optional 3D surface.
- Network Explorer: actual model graph, tensor shapes, skip connections and live activation maps.
- Training Control Room: approved experiments, streamed logs, loss curves, GPU status and safe cancellation.
- Latency Lab: saved CPU/GPU timing distributions, batch comparisons, throughput and accuracy evidence.
- Native desktop window, automatic loopback engine, Program Files installation, shortcuts and uninstall support. Personal data stays in AppData.

The reference CNN achieved **2.10% global relative L2 error** over 300 held-out fields. On the recorded RTX 4070 Laptop GPU, batch-16 end-to-end inference had a **3.3997 ms median**, **6.7225 ms p95** and **3.798× cross-device median speedup** against the CPU NumPy solver. The CPU CNN was slower than that solver. The reference is a numerical discretization, not an exact analytical solution; the CNN predicts only step 120. See the repository's complete scientific reports for raw evidence and limitations.

## Download and install

Download `NeuralHeat-Studio-Setup.exe`, `SHA256SUMS.txt`, `NeuralHeat-Studio-Third-Party-Notices.txt` and `NeuralHeat-Studio-Certifi-2026.4.22-Source.zip`. Keep the notices and covered source with the installer. The verified setup is **1.813 GB / 1.689 GiB**, contains the full CPU/CUDA application and makes no downloads. Windows 10 1809+ / Windows 11 x64 and preinstalled WebView2 are required. CUDA requires a compatible NVIDIA driver; CPU fallback is included. No separate Python, Node.js or CUDA Toolkit is needed. The unsigned installer may trigger SmartScreen.

The optional `best.pt` asset lets source users load the reference checkpoint after generating its matching dataset. Keep the supplied SHA256 unchanged when sharing that checkpoint.

The Microsoft review is complete and full terms are archived. The Mg-free installer passed actual Program Files installation, CPU/CUDA, training/cancellation, all native workspaces and resizing, shortcuts, AppData and uninstall preservation. Source integrity verified all 2,801 files. The measured setup is **1,813,363,530 bytes (1.813 GB / 1.689 GiB)**; SHA256 is `ecf3f57dcc2f8b50144c42e505559f71550d1f75466c3734aab16ec78d69171f`. The release source corresponds to the verified application; only packaging, licence and publication materials were finalised after freezing.
