# Numerical method, training and benchmarking

Detailed methodology retained from the original scientific project documentation. The current release overview and measured result summary are in [README](../README.md).

## Physical problem and numerical reference

On the square $(x,y)\in[0,1]^2$ with fixed diffusivity $\alpha=0.1$:

$$
\frac{\partial T}{\partial t}=\alpha\left(\frac{\partial^2T}{\partial x^2}+\frac{\partial^2T}{\partial y^2}\right),
\qquad T|_{\partial\Omega}=0.
$$

The grid has 64 nodes per axis, **including the boundary**, so $\Delta x=\Delta y=1/63$. The solver uses the five-point Laplacian and explicit Euler:

$$
T^{n+1}_{i,j}=T^n_{i,j}+r\left(T^n_{i+1,j}+T^n_{i-1,j}+T^n_{i,j+1}+T^n_{i,j-1}-4T^n_{i,j}\right),
\quad r=\frac{\alpha\Delta t}{\Delta x^2}.
$$

The 2D stability restriction is $\alpha\Delta t(\Delta x^{-2}+\Delta y^{-2})\leq1/2$, or $r\leq1/4$ on this square grid. By default $\Delta t=0.9\Delta x^2/(4\alpha)\approx5.66893424\times10^{-4}$, $r=0.225$, and 120 steps reach $t\approx0.06802721$. Unstable user-specified steps are rejected.

The implementation copies its input, projects its boundary to zero, vectorizes leading batch dimensions, and alternates between two float32 state buffers. It does not clip values to conceal instability. Space and time truncation errors are $O(\Delta x^2)$ and $O(\Delta t)$. The targets are **numerical reference solutions**, not exact analytical solutions. A separate sine-mode test uses a known analytical solution only to test grid refinement.

Dirichlet boundaries are a heat sink: total heat generally decreases. Conservation of heat would be inappropriate to require here. The solver tests cover CFL rejection, zero input, boundary conditions, batch consistency, input immutability, a maximum principle, impulse symmetry and spreading, boundary heat loss, discrete eigenmode decay, and refinement toward a continuum sine solution.

## Dataset and normalization

| Configuration | Train | Validation | Held-out test | Epoch limit |
|---|---:|---:|---:|---:|
| `configs/full.json` | 2,000 | 300 | 300 | 80 |
| `configs/smoke.json` | 64 | 16 | 64 | 3 |

Both configurations retain the full 64×64 grid and 120-step physics. Smoke training checks execution; its small dataset and three epochs cannot establish model quality.

Each input sums 1–5 Gaussians, with independently sampled centers in $[0.12,0.88]^2$, amplitudes in $[0.4,1.6]$, and isotropic standard deviations in $[0.04,0.16]$ domain lengths. Edges are set to zero before solving. This projection can create initial boundary layers near sources.

NumPy generators use `SeedSequence([root_seed, split_id, sample_id])`. Hashes check that no identical input occurs across splits. Training and validation never use the held-out test labels for parameter selection. Separate smoke/full seeds prevent confusing their results.

Raw inputs and targets are cached as float32 `.npy` files under `data/<dataset_id>/`, suitable for memory mapping. The dataset ID hashes physics, counts, seeds, generator version, source distribution, and normalization convention. Metadata includes all file SHA256 checksums, generation time, solver time, and split sizes. Generation is serial with batches of up to 64; metadata is published atomically only when all files exist. Do not run two generators concurrently against the same cache directory. Bump the generator version when changing the algorithm.

One positive scalar—the **maximum training input temperature**—normalizes both inputs and targets. Validation and test data do not fit this scalar and are not clipped to $[0,1]$. Evaluation reverses scaling and reports errors in original temperature units. `neuralheat-data --verify` and evaluation verify cached checksums. `--force` regenerates a cache explicitly.

## Surrogate architecture and training

The small residual U-Net has two convolutions per block, 3×3 kernels, GELU activations, and channels `8 → 16 → 32 → 16 → 8`. Average pooling reduces spatial resolution twice. Nearest-neighbor upsampling and concatenated encoder skips reconstruct the field. A 1×1 linear head predicts a correction to the initial field; it starts at zero so the initial predictor is the identity baseline. The final boundary projection guarantees exact zero edges. Inputs and outputs have one channel.

MSE loss and Adam train the model. Validation runs after each epoch. Every strict validation improvement atomically saves `best.pt`; patience resets require improvement exceeding `min_delta`. Defaults are batch size 64, learning rate 0.001, patience 12, and four CPU threads. The test set is evaluated only after training. The best checkpoint stores weights, Adam state, epoch, configuration, scaling, dataset ID, and loss history. `training.json` stores the full history, checkpoint hash, actual epoch count, best validation loss, parameter count, and elapsed training time. This implementation starts fresh for every training command; it does not expose resume training.

Device `auto` chooses CUDA when available and CPU otherwise. Seeds cover Python, NumPy, PyTorch, and data shuffling. Deterministic PyTorch algorithms are enabled, cuDNN autotuning and TF32 are disabled. Nearest upsampling avoids the CUDA determinism restrictions of some interpolating backward kernels. Reproducibility within a fixed environment is the goal; bitwise equivalence across releases and hardware is not promised.

## Install and reproduce

Use Python **3.12** for a conservative wheel-compatible setup. The package supports Python 3.10+ where its dependencies provide compatible wheels. Run commands from the repository root in a network-enabled environment.

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python scripts/check_environment.py
python -m pytest -q
```

For CPU-only PyTorch, install it from the [official CPU wheel index](https://download.pytorch.org/whl/cpu) before the editable package install:

```bash
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
```

For CUDA, use the wheel command appropriate to your driver and platform from the [official PyTorch installation selector](https://pytorch.org/get-started/locally/). A system `nvidia-smi` CUDA capability is distinct from `torch.version.cuda` and `torch.cuda.is_available()`.

Run the whole experiment, including tests, cached generation, training, evaluation, and benchmarking:

```bash
# Small execution check, with artifacts isolated from a full run:
python scripts/run_experiment.py --config configs/smoke.json --output-root runs/smoke

# Full dataset and training; canonical models/, reports/, figures/ outputs:
python scripts/run_experiment.py --config configs/full.json

# Force a CPU-only experiment:
python scripts/run_experiment.py --config configs/smoke.json --output-root runs/smoke-cpu --device cpu --skip-cuda
```

The runner saves step logs, return codes, and wall times in `reports/execution.json`. It checks dependencies before starting, fails on an unsuccessful step, and records missing dependencies as a blocked run. Each successful benchmark records installed package versions and build information; archive `reports/environment.json`, all configuration files, checkpoints, cached data metadata, and generated reports together. The project supplies dependency compatibility ranges, not a tested resolved dependency lock: the initial offline environment could not resolve or validate one. Capture a resolved installation with `python -m pip freeze > reports/requirements-resolved.txt` for subsequent recreation on the same platform.

Individual commands allow investigation and tuning:

```bash
neuralheat-data --config configs/full.json --verify
neuralheat-train --config configs/full.json --epochs 80 --batch-size 64 --learning-rate 0.001 --device auto
neuralheat-evaluate --config configs/full.json --checkpoint models/best.pt --device auto
neuralheat-benchmark --config configs/full.json --checkpoint models/best.pt --warmup 10 --repeats 100 --threads 1 --batch-sizes 1 16 64
```

Equivalent module entry points are `python -m neuralheat.dataset`, `.train`, `.evaluate`, and `.benchmark`. Training supports `--output` and `--figures-dir`; evaluation supports `--output`, `--data-dir`, `--batch-size`, `--threads`, and `--figures-dir`; benchmarking supports `--data-dir`, `--reports-dir`, `--figures-dir`, and `--skip-cuda`. Use the same data-affecting configuration as the checkpoint: mismatches are rejected. Changing training hyperparameters does not invalidate cached fields. Keep smoke and full models/reports in separate directories.

## Held-out accuracy

The CNN and identity baseline $\hat T=T_0$ are scored on exactly the same numerical references. Float64 reductions limit accumulation error; fields themselves remain float32. Metrics include all grid nodes, including the zero edges:

- MSE, RMSE, and MAE over every test pixel.
- Global relative L2: $\|\hat T-T_{\mathrm{ref}}\|_2/\max(\|T_{\mathrm{ref}}\|_2,10^{-12})$ over all fields concatenated.
- Mean per-sample relative L2, maximum per-sample relative L2, and its sample index.
- Worst-case per-sample RMSE and its index, maximum pointwise absolute error, signed mean error (bias), and negative prediction fraction.

MAE is the mean absolute error against the numerical solver; signed mean error is reported separately because cancellation can hide large errors. The identity baseline establishes whether learning improves over doing no diffusion. It is not used as an alternative numerical method in latency speedup calculations.

`figures/accuracy_comparison.png` shows sample 0 and the worst-RMSE test sample with initial field, numerical output, CNN output, and absolute error. The three temperature panels share a scale within each row; errors have their own color scale. `figures/training_loss.png` shows training and validation MSE. Neither is supplied until an actual run produces it.

## Latency lab methodology

All methods solve the same fixed-time mapping on the same contiguous float32 test fields at batch sizes **1, 16, 64**. The NumPy solver vectorizes the batch. CPU CNN measurements always run; CUDA CNN measurements run when PyTorch detects CUDA unless `--skip-cuda` is set.

| Scope | Input → output | Included |
|---|---|---|
| Numerical solver | Raw CPU NumPy → owned raw CPU NumPy | Input copy, boundary enforcement, allocations, 120 updates |
| Model forward | Normalized resident device tensor → normalized device tensor | Model forward and output allocations |
| End-to-end prediction | Raw CPU NumPy → owned raw CPU NumPy | Tensor wrapping, normalization, device transfers when required, forward, inverse scaling, CPU output copy |

Training, target generation, checkpoint loading, cache/disk reads, accuracy calculation, and plotting are excluded from all inference scopes. Offline generation and training costs appear separately. Training time covers epoch loops, validation, and checkpoint writing; it excludes data generation and model construction.

The benchmark uses `model.eval()` and `torch.inference_mode()`. Full defaults are 10 warmups per task, then 100 individual measurements per task. Measurement order is deterministically shuffled each repetition to reduce systematic ordering effects. `perf_counter_ns` measures host-observed wall time; CUDA synchronizes before the timer and before stopping it. This correctly waits for asynchronous device execution, while including the final synchronization overhead. These are **synchronized forward latencies**, not CUDA-event kernel-only durations. Input tensors for the forward scope are prepared outside timing.

Reports include median, mean, p95 (linear interpolation), sample standard deviation (`ddof=1`), and every raw measurement. Throughput is `batch_size / mean_batch_seconds`; latency is per batch, not per sample. CPU PyTorch intraop threads default to 1 for benchmarking and are adjustable. NumPy uses an elementwise stencil rather than BLAS. The reports record actual PyTorch thread settings, package versions, CPU/GPU names, driver inventory, CUDA/cuDNN versions, build flags, and numerical configuration.

For equal batches, **speedup = NumPy solver median / CNN end-to-end median**. CPU-vs-CPU and CPU-solver-vs-CUDA comparisons have explicit separate labels. Values below 1 are slowdowns. Resident-forward time is diagnostic and is never substituted into this speedup. No outcome assumes that the surrogate is faster or sufficiently accurate. `figures/latency_comparison.png` plots measured medians on log axes; JSON retains the distribution.

After a successful run:

```text
reports/benchmark.json       Full measurements, raw timings, hardware and provenance
reports/benchmark.csv        One row per method, scope and batch
reports/benchmark.md         Human-readable accuracy, timing and limitations
reports/evaluation.json      Held-out metrics and identity comparison
reports/environment.json     Installed distributions and runtime inspection
reports/execution.json       Actual commands, statuses and offline step wall times
figures/accuracy_comparison.png
figures/latency_comparison.png
figures/training_loss.png
models/best.pt
models/training.json
```

## Limitations and interpretation

The learned operator is specialized to the training distribution, one diffusivity, one final time, one spatial resolution, and homogeneous Dirichlet boundaries. It is not an autoregressive or parameterized PDE solver. No positivity, linearity, energy dissipation, conservation, or stability guarantee follows from MSE training; only the edges are enforced exactly. Accuracy on other source families, signs, scales, geometries, or times requires separate validation and probably retraining.

Accuracy is relative to a finite-grid reference that has its own truncation and rounding errors. Refinement tests do not make all generated labels exact. A speedup over this explicit NumPy stencil does not establish an advantage over optimized compiled stencils, implicit methods, FFT/spectral solvers, or a GPU numerical solver. The repeated workload uses warm fixed batches, not cold starts, network serving, concurrency, or I/O. Laptop thermals, clocks, power state, scheduler noise, and background load remain uncontrolled. p95 from few smoke repeats is weak evidence; full repeats and raw timing inspection are preferable. Training and label-generation cost must be amortized over enough useful predictions before deployment is worthwhile.

## Project layout and checks

```text
src/neuralheat/   solver.py dataset.py model.py train.py evaluate.py
                 benchmark.py visualization.py common.py
tests/           solver, architecture, dataset integrity, metrics, early stopping,
                 checkpoint/evaluation/report round-trip, configuration contracts
configs/         smoke.json full.json
scripts/         check_environment.py run_experiment.py
models/          Best checkpoint and complete training history after a run
figures/         Workflow schematic and generated scientific figures
reports/         Actual run status and generated reports
```

```bash
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python -m pytest -q -rs
```

The integration test uses small real arrays and an actual two-epoch CPU training run, then verifies evaluation, timing statistics, speedups, report files, and PNG generation. It does not assert a favorable speedup or training outcome. Missing scientific dependencies skip their entire test modules; a passing exit status with skips is not evidence that the scientific suite ran. The experiment runner prevents that ambiguity with a dependency preflight. A GitHub Actions CPU workflow is included but has not been executed in this workspace.

## Interview explanation

**Solver:** “I discretize the Laplacian with a five-point stencil and advance explicit Euler. The 2D CFL limit makes each interior update a stable weighted average. Boundary nodes stay zero, so heat can leave the domain. My labels are numerical approximations; eigenmode and refinement tests check the implementation independently.”

**CNN:** “I learn the initial-to-final temperature map with a small residual U-Net. The encoder captures diffusion over a wider spatial neighborhood, skips retain location information, and the decoder predicts a correction to the identity baseline. Training uses MSE and validation early stopping; test data are isolated and normalization uses training data only.”

**Benchmark:** “I measure the same mapping at matched batch sizes. Resident forward time isolates model computation; end-to-end time includes scaling and transfers. CUDA timing waits for completion. I retain warmups, repeated raw timings, tail latency, hardware metadata, and separate CPU versus cross-device speedups. I judge useful acceleration jointly with held-out error and offline costs.”

## References and license

- [PyTorch benchmarking methodology](https://docs.pytorch.org/tutorials/recipes/recipes/benchmark.html) explains warmups, thread control, and synchronization.
- [PyTorch deterministic algorithms](https://docs.pytorch.org/docs/stable/generated/torch.use_deterministic_algorithms.html) documents supported operations and restrictions.
- [NumPy random generation](https://numpy.org/doc/stable/reference/random/index.html) describes `Generator` and `SeedSequence`.

MIT licensed; see [LICENSE](../LICENSE).
