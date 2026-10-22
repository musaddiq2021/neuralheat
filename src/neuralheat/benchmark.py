"""Synchronized, randomized-order latency measurements and provenance reports."""

import argparse
import csv
import importlib.metadata
import logging
import os
import platform
import subprocess
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter_ns

import numpy as np
import torch

from .common import read_config, seed_everything, setup_logging, write_json
from .dataset import generate
from .evaluate import evaluate, load_model, predict
from .solver import SolverConfig, solve
from .visualization import plot_latency


def hardware_metadata() -> dict:
    cpu = platform.processor() or "unknown"
    if platform.system() == "Linux" and Path("/proc/cpuinfo").exists():
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    if platform.system() == "Windows":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            ) as key:
                cpu = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        except OSError:
            pass
    try:
        inventory = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        driver_inventory = inventory.stdout.strip() if inventory.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        driver_inventory = None
    return {
        "cpu": cpu,
        "logical_cpu_count": os.cpu_count(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "numpy": str(np.__version__),
        "pytorch": str(torch.__version__),
        "cuda_build_version": torch.version.cuda,
        "cudnn_version": torch.backends.cudnn.version(),
        "cuda_available": torch.cuda.is_available(),
        "nvidia_driver_inventory": driver_inventory,
        "installed_distributions": sorted(
            f"{item.metadata['Name']}=={item.version}"
            for item in importlib.metadata.distributions()
        ),
        "gpus": [
            {
                "name": torch.cuda.get_device_name(i),
                "memory_bytes": torch.cuda.get_device_properties(i).total_memory,
                "compute_capability": list(torch.cuda.get_device_capability(i)),
            }
            for i in range(torch.cuda.device_count())
        ],
        "torch_num_threads": torch.get_num_threads(),
        "torch_num_interop_threads": torch.get_num_interop_threads(),
        "torch_build": torch.__config__.show(),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "tf32_matmul": torch.backends.cuda.matmul.allow_tf32,
        "tf32_cudnn": torch.backends.cudnn.allow_tf32,
        "environment": {
            key: os.environ.get(key)
            for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")
        },
    }


def summarize(times_ms: list[float], batch_size: int) -> dict:
    """Statistics of individual batch requests, not repeated per-item times."""
    if (
        len(times_ms) < 2
        or batch_size < 1
        or any(not np.isfinite(value) or value <= 0 for value in times_ms)
    ):
        raise ValueError("Need at least two positive finite timings and a positive batch size")
    values = np.asarray(times_ms, dtype=np.float64)
    return {
        "median_ms": float(np.median(values)),
        "mean_ms": float(values.mean()),
        "p95_ms": float(np.percentile(values, 95)),
        "std_ms": float(values.std(ddof=1)),
        "throughput_samples_per_second": float(batch_size * 1000 / values.mean()),
        "raw_times_ms": values.tolist(),
    }


def measure_tasks(
    tasks: dict[str, tuple[Callable[[], object], torch.device | None]],
    warmup: int,
    repeats: int,
    seed: int,
) -> dict[str, list[float]]:
    """Warm each task, then shuffle task order on each measured repetition.

    CUDA uses synchronized wall-clock timing. Synchronization before t0 drains
    prior work, synchronization before t1 waits for completion; its overhead is
    included. This measures host-observed latency rather than kernel-only time.
    """
    if warmup < 1 or repeats < 2:
        raise ValueError("warmup must be >=1 and repeats >=2")
    for callback, device in tasks.values():
        for _ in range(warmup):
            callback()
        if device is not None and device.type == "cuda":
            torch.cuda.synchronize(device)
    rng = np.random.default_rng(seed)
    results: dict[str, list[float]] = {name: [] for name in tasks}
    for _ in range(repeats):
        for name in rng.permutation(list(tasks)):
            callback, device = tasks[name]
            if device is not None and device.type == "cuda":
                torch.cuda.synchronize(device)
            before = perf_counter_ns()
            output = callback()
            if device is not None and device.type == "cuda":
                torch.cuda.synchronize(device)
            elapsed = (perf_counter_ns() - before) / 1e6
            results[name].append(elapsed)
            # Release output outside the measured interval. Every request still
            # includes output allocation, like a normal inference call.
            del output
    return results


def speedup_rows(rows: list[dict]) -> list[dict]:
    """Compare matched batch sizes using solver median / end-to-end median."""
    result = []
    for row in rows:
        if row["scope"] != "end_to_end":
            continue
        solver = next(
            item
            for item in rows
            if item["method"] == "numpy_cpu_solver" and item["batch_size"] == row["batch_size"]
        )
        result.append(
            {
                "method": row["method"],
                "batch_size": row["batch_size"],
                "comparison": "cpu_vs_cpu"
                if row["device"] == "cpu"
                else "cross_device_cpu_solver_vs_cuda_surrogate",
                "speedup": solver["median_ms"] / row["median_ms"],
            }
        )
    return result


def write_reports(report: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "benchmark.json", report)
    columns = [
        "method",
        "device",
        "scope",
        "batch_size",
        "warmup",
        "repeats",
        "median_ms",
        "mean_ms",
        "p95_ms",
        "std_ms",
        "throughput_samples_per_second",
        "speedup",
        "comparison",
    ]
    speedups = {(item["method"], item["batch_size"]): item for item in report["speedups"]}
    with (directory / "benchmark.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in report["latency"]:
            writer.writerow({**row, **speedups.get((row["method"], row["batch_size"]), {})})
    hw, accuracy = report["hardware"], report["accuracy"]
    lines = [
        "# NEURALHEAT measured benchmark",
        "",
        f"Run: {report['timestamp_utc']} ({report['config_name']}).",
        f"Dataset: `{accuracy['dataset_id']}`; checkpoint SHA256: `{accuracy['checkpoint_sha256']}`.",
        "",
        "## Environment",
        "",
        f"CPU: {hw['cpu']} ({hw['logical_cpu_count']} logical CPUs); PyTorch threads: {hw['torch_num_threads']}.",
        f"GPU(s): {hw['gpus'] or 'none'}. Python {hw['python']}; NumPy {hw['numpy']}; PyTorch {hw['pytorch']}; CUDA build {hw['cuda_build_version']}.",
        f"Platform: {hw['platform']}. Parameters: {accuracy['parameter_count']}.",
        "",
        "## Numerical reference",
        "",
        f"Configuration: `{report['numerical']}`.",
        "Five-point finite differences, explicit Euler, float32, zero Dirichlet boundaries. This is a numerical reference, not an exact analytical solution.",
        "",
        "## Held-out accuracy",
        "",
        "Metrics are in original temperature units; relative errors are dimensionless. Reductions include zero boundary pixels.",
        "",
        "| Method | MSE | RMSE | MAE | Relative L2 | Worst sample RMSE | Mean signed error |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key in ("surrogate", "identity_baseline"):
        value = accuracy[key]
        lines.append(
            f"| {key} | {value['mse']:.6g} | {value['rmse']:.6g} | {value['mae']:.6g} | {value['relative_l2']:.6g} | {value['worst_sample_rmse']:.6g} | {value['mean_signed_error']:.6g} |"
        )
    lines += [
        "",
        "## Latency",
        "",
        "All times are per batch in milliseconds. Standard deviation uses ddof=1; p95 uses linear percentile interpolation.",
        "",
        "| Method | Batch | Median ms | Mean ms | p95 ms | Std ms | Samples/s |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["latency"]:
        lines.append(
            f"| {row['method']} | {row['batch_size']} | {row['median_ms']:.5g} | {row['mean_ms']:.5g} | {row['p95_ms']:.5g} | {row['std_ms']:.5g} | {row['throughput_samples_per_second']:.5g} |"
        )
    lines += [
        "",
        "Speedup = matched-batch NumPy solver median / surrogate end-to-end median; values below 1 mean the surrogate is slower.",
        "",
    ]
    for row in report["speedups"]:
        lines.append(
            f"- Batch {row['batch_size']}, {row['comparison']}: **{row['speedup']:.3f}x**."
        )
    training = accuracy["training"]
    lines += [
        "",
        "## Separate offline costs",
        "",
        f"Dataset generation: {accuracy['dataset']['generation_seconds']:.3f} s (solver portion {accuracy['dataset']['solver_seconds']:.3f} s), recorded when the cache was created.",
        (
            f"Training: {training['training_seconds']:.3f} s; {training['epochs_executed']} epochs; best epoch {training['best_epoch']} on {training['device']}."
            if training
            else "Training timing unavailable: training.json was not supplied with this checkpoint."
        ),
        "",
        "## Method and interpretation",
        "",
        *report["methodology"],
        "",
        *report["interpretation"],
        "",
        "## Limitations",
        "",
        *report["limitations"],
        "",
        "Raw timings, complete metrics, software build flags, and provenance are in benchmark.json.",
    ]
    (directory / "benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def benchmark(
    config: dict,
    checkpoint_path: Path,
    data_dir: Path,
    reports_dir: Path,
    figures_dir: Path,
    *,
    skip_cuda: bool = False,
) -> dict:
    settings = config["benchmark"]
    if (
        settings["threads"] < 1
        or not settings["batch_sizes"]
        or any(value < 1 for value in settings["batch_sizes"])
    ):
        raise ValueError("Need positive thread count and batch sizes")
    if len(set(settings["batch_sizes"])) != len(settings["batch_sizes"]):
        raise ValueError("Batch sizes must be unique")
    if settings["warmup"] < 1 or settings["repeats"] < 2:
        raise ValueError("warmup must be >=1 and repeats >=2")
    seed_everything(config["seed"])
    torch.set_num_threads(settings["threads"])
    # No evaluation/data generation/plotting belongs inside any timed callback.
    accuracy = evaluate(
        checkpoint_path, config, data_dir, "cpu" if skip_cuda else "auto", figures_dir=figures_dir
    )
    path, metadata = generate(config, data_dir)
    initial = np.load(path / "test_inputs.npy", mmap_mode="r")
    physics = SolverConfig(**config["physics"])
    devices = [torch.device("cpu")]
    if torch.cuda.is_available() and not skip_cuda:
        devices.append(torch.device("cuda:0"))
    models = {str(device): load_model(checkpoint_path, device)[0] for device in devices}
    rows: list[dict] = []
    parity = None
    with torch.inference_mode():
        if len(devices) == 2:
            probe = np.array(initial[:1], copy=True)
            parity = float(
                np.abs(
                    predict(models["cpu"], probe, metadata["normalization_scale"], devices[0])
                    - predict(models["cuda:0"], probe, metadata["normalization_scale"], devices[1])
                ).max()
            )
        for batch_size in settings["batch_sizes"]:
            if batch_size > len(initial):
                raise ValueError(
                    "Test dataset smaller than requested batch; use more held-out samples"
                )
            raw = np.array(initial[:batch_size], copy=True)
            tasks = {"numpy_cpu_solver": (lambda fields=raw: solve(fields, physics), None)}
            resident = {}
            for device in devices:
                name = str(device)
                model = models[name]
                resident[name] = (
                    torch.from_numpy(raw[:, None].copy()).to(device)
                    / metadata["normalization_scale"]
                )
                tasks[f"torch_{device.type}_forward"] = (
                    lambda m=model, t=resident[name]: m(t),
                    device,
                )
                tasks[f"torch_{device.type}_end_to_end"] = (
                    lambda m=model, d=device, fields=raw: predict(
                        m, fields, metadata["normalization_scale"], d
                    ),
                    device,
                )
            measured = measure_tasks(
                tasks, settings["warmup"], settings["repeats"], config["seed"] + batch_size
            )
            for name, times in measured.items():
                scope = (
                    "solver"
                    if name == "numpy_cpu_solver"
                    else "end_to_end"
                    if name.endswith("end_to_end")
                    else "forward"
                )
                row = {
                    "method": name,
                    "device": "cuda" if "cuda" in name else "cpu",
                    "scope": scope,
                    "batch_size": batch_size,
                    "warmup": settings["warmup"],
                    "repeats": settings["repeats"],
                    **summarize(times, batch_size),
                }
                rows.append(row)
                logging.info("%s batch %d median %.4f ms", name, batch_size, row["median_ms"])
    speedups = speedup_rows(rows)
    mse_better = accuracy["surrogate"]["mse"] < accuracy["identity_baseline"]["mse"]
    report = {
        "status": "completed",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "config_name": config["name"],
        "config": config,
        "hardware": hardware_metadata(),
        "numerical": physics.metadata(),
        "accuracy": accuracy,
        "latency": rows,
        "speedups": speedups,
        "cpu_cuda_max_abs_difference_probe": parity,
        "cuda_benchmarked": len(devices) == 2,
        "methodology": [
            f"Each task has {settings['warmup']} warmups and {settings['repeats']} individually timed calls. Task order is deterministically shuffled each repetition; all calls are serial.",
            "perf_counter_ns with CUDA synchronization before timing and before stop; synchronization overhead is included. No asynchronous launches are mistaken for completed inference.",
            "Forward: normalized resident device tensor to normalized device tensor. End-to-end: raw contiguous CPU float32 NumPy input to independently owned CPU NumPy output, including normalization, transfers and inverse scaling.",
            "Solver: raw CPU NumPy input to owned CPU NumPy output, including input copy, boundary enforcement, two state buffers and all time steps; vectorized across the same batch.",
            "Both torch paths use eval() and inference_mode(), float32, deterministic algorithms, TF32 disabled, fixed CPU intraop threads. No torch.compile, mixed precision or pinned transfers.",
            "Throughput = batch size / mean batch time; speedup = solver median / end-to-end median for matching batch. Training, data generation, model loading, evaluation and plotting are excluded.",
        ],
        "interpretation": [
            f"Held-out surrogate MSE is {'lower' if mse_better else 'not lower'} than the identity baseline; timing speedup alone does not establish scientific usefulness.",
            *[
                f"Batch {item['batch_size']} {item['comparison']}: surrogate {'faster' if item['speedup'] > 1 else 'slower or equal'} ({item['speedup']:.3f}x)."
                for item in speedups
            ],
        ],
        "limitations": [
            "Only Gaussian-source inputs at one alpha, grid, boundary condition and final time are trained. The CNN is not a general PDE solver; it has no guaranteed positivity, conservation, stability or out-of-distribution accuracy.",
            "Targets have first-order temporal and second-order spatial truncation error plus float32 rounding. Hard-zeroed Gaussian edge values can create initial boundary layers.",
            "This is an explicit NumPy stencil baseline, not a comparison against every optimized implicit, FFT, spectral, compiled or GPU solver.",
            "Warm, fixed input batches measure a serial in-memory workload; disk I/O, network service overhead, cold start, concurrency and deployment costs are excluded. OS scheduling, thermals, clocks and other workloads remain uncontrolled.",
            "Cross-device speedups use additional hardware and are labeled separately. CPU thread setting controls PyTorch; this NumPy elementwise stencil uses no BLAS, so its effective scheduling differs.",
            "Per-call synchronization affects short CUDA timings; p95 is descriptive and less reliable with few repeats. Raw samples are retained for inspection. Reproducibility across library/hardware versions is not bitwise guaranteed.",
        ],
    }
    plot_latency(rows, figures_dir / "latency_comparison.png")
    write_reports(report, reports_dir)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/full.json"))
    parser.add_argument("--checkpoint", type=Path, default=Path("models/best.pt"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--figures-dir", type=Path, default=Path("figures"))
    parser.add_argument("--skip-cuda", action="store_true")
    parser.add_argument("--warmup", type=int)
    parser.add_argument("--repeats", type=int)
    parser.add_argument("--threads", type=int)
    parser.add_argument("--batch-sizes", type=int, nargs="+")
    args = parser.parse_args()
    setup_logging()
    config = read_config(args.config)
    for key in ("warmup", "repeats", "threads", "batch_sizes"):
        value = getattr(args, key)
        if value is not None:
            config["benchmark"][key] = value
    benchmark(
        config,
        args.checkpoint,
        args.data_dir,
        args.reports_dir,
        args.figures_dir,
        skip_cuda=args.skip_cuda,
    )


if __name__ == "__main__":
    main()
