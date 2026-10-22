# Actual Windows interface captures

The maintainer supplied four screenshots on 22 October 2026 from the running NeuralHeat Studio desktop application. Each was visually inspected before publication. These are manual captures, not generated mockups or an automated API/checkpoint verification record.

| Published image | View | Dimensions | Original bytes | Published bytes |
|---|---|---:|---:|---:|
| [overview.png](overview.png) | System Overview; saved accuracy, losses and batch-one latency | 1899 × 982 | 224,374 | 205,290 |
| [physics.png](physics.png) | Initial field, numerical step 120 and source controls | 1902 × 977 | 215,621 | 184,181 |
| [network.png](network.png) | Actual graph with Encoder 01 selected | 1902 × 984 | 234,721 | 214,910 |
| [loading.png](loading.png) | Native desktop startup | 1916 × 1016 | 48,875 | 44,203 |

Together: **723,591 → 648,584 bytes**, a **10.37%** reduction. Compression is lossless: no cropping, resizing, palette quantization, retouching or generated content. Decoded RGBA pixels were compared byte for byte. Original `Screenshot*.png` files remain locally intact and are excluded from Git to avoid publishing duplicate images. The clean filenames are GitHub-compatible relative paths.

[provenance.json](provenance.json) records original and optimized SHA256 hashes, dimensions, pixel hashes and the scope of this evidence. The maintainer approved using the available captures: no separate Training Control Room or Latency Lab screenshot was supplied. The Overview shows their saved summary charts. Physics/CNN/error panels and network nodes outside the captured viewport are not claimed to be visible.

To reproduce this compression from the original local files:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_screenshots.py
```

An optional automated capture helper remains available for future updates:

```powershell
.\.venv\Scripts\python.exe scripts/capture_release_screenshots.py
```

It requires the existing portable assets, development dependencies and a supported browser. Its `capture.json`, when generated successfully, is separate from the current manual `provenance.json`. Do not describe manual captures as automated test results. Neither screenshot preparation nor documentation review starts training or rebuilds the application.
