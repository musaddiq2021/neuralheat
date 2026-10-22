import copy
import json
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
torch = pytest.importorskip("torch")
pytest.importorskip("matplotlib")
from neuralheat.benchmark import benchmark, summarize
from neuralheat.common import file_sha256
from neuralheat.dataset import HeatDataset, generate, verify_cache
from neuralheat.evaluate import accuracy_metrics, evaluate
from neuralheat.train import EarlyStopping, train


@pytest.fixture
def tiny_config() -> dict:
    return {
        "name": "test",
        "seed": 12,
        "physics": {"grid_size": 16, "alpha": 0.1, "steps": 6},
        "data": {"train": 8, "validation": 4, "test": 4},
        "model": {"base_channels": 2},
        "training": {
            "epochs": 2,
            "batch_size": 4,
            "learning_rate": 0.001,
            "patience": 2,
            "min_delta": 1e-8,
            "threads": 1,
        },
        "benchmark": {"batch_sizes": [1, 4], "warmup": 1, "repeats": 3, "threads": 1},
    }


def test_cache_reproduction_disjointness_scaling_and_integrity(
    tmp_path: Path, tiny_config: dict
) -> None:
    first, metadata = generate(tiny_config, tmp_path / "first")
    second, repeated = generate(tiny_config, tmp_path / "second")
    assert metadata["sha256"] == repeated["sha256"]
    assert metadata["unique_input_count"] == 16
    assert metadata["normalization_scale"] == float(np.load(first / "train_inputs.npy").max())
    normalized, _ = HeatDataset(first, "train", metadata["normalization_scale"])[0]
    assert normalized.dtype == torch.float32 and normalized.shape == (1, 16, 16)
    assert (
        generate(tiny_config, tmp_path / "first")[1]["generation_seconds"]
        == metadata["generation_seconds"]
    )
    verify_cache(second, repeated, checksums=True)
    changed = np.load(second / "test_targets.npy", mmap_mode="r+")
    changed[0, 1, 1] += 1
    changed.flush()
    del changed
    with pytest.raises(ValueError, match="checksum"):
        verify_cache(second, repeated, checksums=True)


def test_metrics_known_errors_and_zero_target() -> None:
    target = np.ones((2, 4, 4), dtype=np.float32)
    metrics = accuracy_metrics(2 * target, target)
    for key in ("mse", "rmse", "mae", "relative_l2", "worst_sample_rmse", "mean_signed_error"):
        assert metrics[key] == pytest.approx(1)
    assert accuracy_metrics(target * 0, target * 0)["relative_l2"] == 0


def test_early_stopping_saves_strict_best_but_uses_significant_patience() -> None:
    stopper = EarlyStopping(patience=2, min_delta=0.1)
    assert stopper.update(1.0)
    assert stopper.update(0.95)
    assert not stopper.stopped
    assert not stopper.update(1.0)
    assert stopper.stopped and stopper.best == 0.95


def test_timing_statistics() -> None:
    result = summarize([1, 2, 3, 4, 5], batch_size=16)
    assert result["median_ms"] == 3
    assert result["p95_ms"] == pytest.approx(4.8)
    assert result["std_ms"] == pytest.approx(np.std([1, 2, 3, 4, 5], ddof=1))
    assert result["throughput_samples_per_second"] == pytest.approx(16000 / 3)
    with pytest.raises(ValueError):
        summarize([0], 1)


def test_real_training_evaluation_and_benchmark_roundtrip(
    tmp_path: Path, tiny_config: dict
) -> None:
    data, models, figures, reports = [
        tmp_path / name for name in ("data", "models", "figures", "reports")
    ]
    training = train(tiny_config, data, models, "cpu", figures)
    assert training["epochs_executed"] == 2
    assert training["best_validation_mse_normalized"] == min(
        row["validation"] for row in training["history"]
    )
    checkpoint = models / "best.pt"
    assert training["checkpoint_sha256"] == file_sha256(checkpoint)
    report = benchmark(tiny_config, checkpoint, data, reports, figures, skip_cuda=True)
    assert report["status"] == "completed"
    assert len(report["latency"]) == 6
    for speedup in report["speedups"]:
        rows = {
            row["method"]: row
            for row in report["latency"]
            if row["batch_size"] == speedup["batch_size"]
        }
        assert speedup["speedup"] == pytest.approx(
            rows["numpy_cpu_solver"]["median_ms"] / rows[speedup["method"]]["median_ms"]
        )
    assert (
        json.loads((reports / "benchmark.json").read_text())["accuracy"]["surrogate"][
            "test_samples"
        ]
        == 4
    )
    for name in ("accuracy_comparison.png", "latency_comparison.png", "training_loss.png"):
        assert (figures / name).stat().st_size > 1000
    mismatch = copy.deepcopy(tiny_config)
    mismatch["seed"] += 1
    with pytest.raises(ValueError, match="do not match"):
        evaluate(checkpoint, mismatch, data, "cpu", figures_dir=figures)
