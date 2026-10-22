# NEURALHEAT measured benchmark

Run: 2026-10-21T12:41:39.080098+00:00 (full).
Dataset: `2936c8f836eddf5b`; checkpoint SHA256: `d5e2d5a88c8666101279d696f04aa32c53159399938de126642e3e745c4429d2`.

## Environment

CPU: Intel(R) Core(TM) Ultra 9 185H (22 logical CPUs); PyTorch threads: 1.
GPU(s): [{'name': 'NVIDIA GeForce RTX 4070 Laptop GPU', 'memory_bytes': 8585216000, 'compute_capability': [8, 9]}]. Python 3.12.10; NumPy 2.5.4; PyTorch 2.11.0+cu128; CUDA build 12.8.
Platform: Windows-11-10.0.26200-SP0. Parameters: 29617.

## Numerical reference

Configuration: `{'grid_size': 64, 'alpha': 0.1, 'steps': 120, 'length': 1.0, 'cfl_safety': 0.9, 'dt': None, 'dx': 0.015873015873015872, 'effective_dt': 0.0005668934240362811, 'final_time': 0.06802721088435373, 'alpha_dt_over_dx2': 0.225}`.
Five-point finite differences, explicit Euler, float32, zero Dirichlet boundaries. This is a numerical reference, not an exact analytical solution.

## Held-out accuracy

Metrics are in original temperature units; relative errors are dimensionless. Reductions include zero boundary pixels.

| Method | MSE | RMSE | MAE | Relative L2 | Worst sample RMSE | Mean signed error |
|---|---:|---:|---:|---:|---:|---:|
| surrogate | 3.62903e-05 | 0.00602414 | 0.00350111 | 0.0210064 | 0.0167287 | 0.000936116 |
| identity_baseline | 0.0273268 | 0.165308 | 0.0815496 | 0.576436 | 0.326628 | 0.0322725 |

## Latency

All times are per batch in milliseconds. Standard deviation uses ddof=1; p95 uses linear percentile interpolation.

| Method | Batch | Median ms | Mean ms | p95 ms | Std ms | Samples/s |
|---|---:|---:|---:|---:|---:|---:|
| numpy_cpu_solver | 1 | 1.627 | 1.7265 | 2.0793 | 0.55742 | 579.2 |
| torch_cpu_forward | 1 | 2.1671 | 2.2509 | 2.967 | 0.33979 | 444.27 |
| torch_cpu_end_to_end | 1 | 2.2557 | 2.306 | 2.9331 | 0.30206 | 433.65 |
| torch_cuda_forward | 1 | 1.2344 | 1.5245 | 2.4165 | 0.59997 | 655.96 |
| torch_cuda_end_to_end | 1 | 1.541 | 1.7621 | 2.6942 | 0.64012 | 567.51 |
| numpy_cpu_solver | 16 | 12.911 | 13.044 | 14.587 | 0.92547 | 1226.6 |
| torch_cpu_forward | 16 | 21.921 | 22.154 | 24.274 | 1.0962 | 722.21 |
| torch_cpu_end_to_end | 16 | 22.229 | 22.244 | 24.38 | 1.1078 | 719.28 |
| torch_cuda_forward | 16 | 2.7981 | 3.2934 | 5.7156 | 1.6924 | 4858.2 |
| torch_cuda_end_to_end | 16 | 3.3997 | 3.9972 | 6.7225 | 1.7931 | 4002.8 |
| numpy_cpu_solver | 64 | 57.919 | 57.916 | 60.692 | 1.8106 | 1105 |
| torch_cpu_forward | 64 | 88.855 | 88.86 | 93.282 | 2.5823 | 720.23 |
| torch_cpu_end_to_end | 64 | 89.627 | 90.035 | 95.874 | 3.137 | 710.83 |
| torch_cuda_forward | 64 | 24.981 | 22.407 | 28.196 | 7.338 | 2856.3 |
| torch_cuda_end_to_end | 64 | 28.763 | 25.744 | 32.29 | 8.3029 | 2486 |

Speedup = matched-batch NumPy solver median / surrogate end-to-end median; values below 1 mean the surrogate is slower.

- Batch 1, cpu_vs_cpu: **0.721x**.
- Batch 1, cross_device_cpu_solver_vs_cuda_surrogate: **1.056x**.
- Batch 16, cpu_vs_cpu: **0.581x**.
- Batch 16, cross_device_cpu_solver_vs_cuda_surrogate: **3.798x**.
- Batch 64, cpu_vs_cpu: **0.646x**.
- Batch 64, cross_device_cpu_solver_vs_cuda_surrogate: **2.014x**.

## Separate offline costs

Dataset generation: 2.885 s (solver portion 2.193 s), recorded when the cache was created.
Training: 36.429 s; 80 epochs; best epoch 80 on cuda.

## Method and interpretation

Each task has 10 warmups and 100 individually timed calls. Task order is deterministically shuffled each repetition; all calls are serial.
perf_counter_ns with CUDA synchronization before timing and before stop; synchronization overhead is included. No asynchronous launches are mistaken for completed inference.
Forward: normalized resident device tensor to normalized device tensor. End-to-end: raw contiguous CPU float32 NumPy input to independently owned CPU NumPy output, including normalization, transfers and inverse scaling.
Solver: raw CPU NumPy input to owned CPU NumPy output, including input copy, boundary enforcement, two state buffers and all time steps; vectorized across the same batch.
Both torch paths use eval() and inference_mode(), float32, deterministic algorithms, TF32 disabled, fixed CPU intraop threads. No torch.compile, mixed precision or pinned transfers.
Throughput = batch size / mean batch time; speedup = solver median / end-to-end median for matching batch. Training, data generation, model loading, evaluation and plotting are excluded.

Held-out surrogate MSE is lower than the identity baseline; timing speedup alone does not establish scientific usefulness.
Batch 1 cpu_vs_cpu: surrogate slower or equal (0.721x).
Batch 1 cross_device_cpu_solver_vs_cuda_surrogate: surrogate faster (1.056x).
Batch 16 cpu_vs_cpu: surrogate slower or equal (0.581x).
Batch 16 cross_device_cpu_solver_vs_cuda_surrogate: surrogate faster (3.798x).
Batch 64 cpu_vs_cpu: surrogate slower or equal (0.646x).
Batch 64 cross_device_cpu_solver_vs_cuda_surrogate: surrogate faster (2.014x).

## Limitations

Only Gaussian-source inputs at one alpha, grid, boundary condition and final time are trained. The CNN is not a general PDE solver; it has no guaranteed positivity, conservation, stability or out-of-distribution accuracy.
Targets have first-order temporal and second-order spatial truncation error plus float32 rounding. Hard-zeroed Gaussian edge values can create initial boundary layers.
This is an explicit NumPy stencil baseline, not a comparison against every optimized implicit, FFT, spectral, compiled or GPU solver.
Warm, fixed input batches measure a serial in-memory workload; disk I/O, network service overhead, cold start, concurrency and deployment costs are excluded. OS scheduling, thermals, clocks and other workloads remain uncontrolled.
Cross-device speedups use additional hardware and are labeled separately. CPU thread setting controls PyTorch; this NumPy elementwise stencil uses no BLAS, so its effective scheduling differs.
Per-call synchronization affects short CUDA timings; p95 is descriptive and less reliable with few repeats. Raw samples are retained for inspection. Reproducibility across library/hardware versions is not bitwise guaranteed.

Raw timings, complete metrics, software build flags, and provenance are in benchmark.json.
