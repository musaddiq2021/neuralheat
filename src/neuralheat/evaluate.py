"""Held-out accuracy in original temperature units, with identity baseline."""

import argparse
import json
import logging
from pathlib import Path
from time import perf_counter

import numpy as np
import torch

from .common import (
    file_sha256,
    read_config,
    resolve_device,
    seed_everything,
    setup_logging,
    write_json,
)
from .dataset import generate, verify_cache
from .model import HeatUNet, parameter_count
from .visualization import plot_accuracy, plot_training


def load_model(checkpoint_path: Path, device: torch.device) -> tuple[HeatUNet, dict]:
    """Load the tensor/primitive checkpoint format without arbitrary pickle code."""
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if checkpoint.get("format_version") != 1:
        raise ValueError("Unsupported checkpoint format")
    model = HeatUNet(**checkpoint["config"]["model"])
    model.load_state_dict(checkpoint["model_state"], strict=True)
    model.to(device).eval()
    return model, checkpoint


def predict(model: HeatUNet, initial: np.ndarray, scale: float, device: torch.device) -> np.ndarray:
    """Raw CPU NumPy -> normalized device tensor -> owned raw CPU NumPy output.

    Caller must enable inference_mode; this function also defines the timed
    end-to-end prediction contract. All fields are float32 and contiguous.
    """
    tensor = torch.from_numpy(np.ascontiguousarray(initial[:, None], dtype=np.float32)).to(device)
    output = model(tensor / scale) * scale
    return output[:, 0].cpu().numpy().copy()


def accuracy_metrics(prediction: np.ndarray, target: np.ndarray) -> dict:
    """Float64 reductions; zero-target relative error uses an absolute 1e-12 floor.

    Global relative L2 is ||all errors||/||all targets||; mean sample relative L2
    is separately reported. Worst-case error is maximum per-sample RMSE.
    """
    if prediction.shape != target.shape or prediction.ndim != 3 or len(target) == 0:
        raise ValueError("Expected matching nonempty (N,H,W) predictions and targets")
    if not np.isfinite(prediction).all() or not np.isfinite(target).all():
        raise ValueError("Accuracy inputs contain nonfinite values")
    difference = prediction.astype(np.float64) - target.astype(np.float64)
    squared = np.square(difference).mean(axis=(1, 2))
    sample_rmse = np.sqrt(squared)
    error_norm = np.linalg.norm(difference.reshape(len(target), -1), axis=1)
    target_norm = np.linalg.norm(target.astype(np.float64).reshape(len(target), -1), axis=1)
    relative = error_norm / np.maximum(target_norm, 1e-12)
    return {
        "mse": float(squared.mean()),
        "rmse": float(np.sqrt(squared.mean())),
        "mae": float(np.abs(difference).mean()),
        "mean_signed_error": float(difference.mean()),
        "relative_l2": float(np.linalg.norm(error_norm) / max(np.linalg.norm(target_norm), 1e-12)),
        "mean_sample_relative_l2": float(relative.mean()),
        "worst_sample_rmse": float(sample_rmse.max()),
        "worst_sample_index": int(sample_rmse.argmax()),
        "worst_sample_relative_l2": float(relative.max()),
        "worst_relative_sample_index": int(relative.argmax()),
        "max_absolute_error": float(np.abs(difference).max()),
        "negative_prediction_fraction": float((prediction < 0).mean()),
        "test_samples": len(target),
    }


def evaluate(
    checkpoint_path: Path,
    config: dict,
    data_dir: Path,
    device_name: str = "auto",
    batch_size: int = 64,
    figures_dir: Path = Path("figures"),
) -> dict:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    seed_everything(config["seed"])
    device = resolve_device(device_name)
    model, checkpoint = load_model(checkpoint_path, device)
    path, metadata = generate(config, data_dir)
    verify_cache(path, metadata, checksums=True)
    if (
        checkpoint["dataset_id"] != metadata["dataset_id"]
        or checkpoint["normalization_scale"] != metadata["normalization_scale"]
    ):
        raise ValueError("Checkpoint and dataset do not match; use the training configuration")
    initial = np.load(path / "test_inputs.npy", mmap_mode="r")
    target = np.load(path / "test_targets.npy", mmap_mode="r")
    predictions = []
    started = perf_counter()
    with torch.inference_mode():
        for start in range(0, len(initial), batch_size):
            # Copy read-only memmap data before exposing it to torch.
            predictions.append(
                predict(
                    model,
                    np.array(initial[start : start + batch_size], copy=True),
                    metadata["normalization_scale"],
                    device,
                )
            )
    prediction = np.concatenate(predictions)
    surrogate = accuracy_metrics(prediction, target)
    baseline = accuracy_metrics(initial, target)
    plot_accuracy(
        initial,
        target,
        prediction,
        surrogate["worst_sample_index"],
        figures_dir / "accuracy_comparison.png",
    )
    training_path = checkpoint_path.parent / "training.json"
    training = (
        json.loads(training_path.read_text(encoding="utf-8")) if training_path.exists() else None
    )
    if training is not None:
        if training.get("checkpoint_sha256") != file_sha256(checkpoint_path):
            raise ValueError("training.json does not match checkpoint SHA256")
        plot_training(training["history"], figures_dir / "training_loss.png")
    else:
        plot_training(checkpoint["history"], figures_dir / "training_loss.png")
    return {
        "surrogate": surrogate,
        "identity_baseline": baseline,
        "mse_improvement_factor": baseline["mse"] / surrogate["mse"]
        if surrogate["mse"] > 0
        else None,
        "metric_units": "original temperature units (MSE squared); relative errors dimensionless",
        "mean_error_definition": "MAE is mean absolute error versus numerical reference; mean_signed_error is signed bias",
        "device": str(device),
        "dataset_id": metadata["dataset_id"],
        "checkpoint_sha256": file_sha256(checkpoint_path),
        "checkpoint_epoch": checkpoint["epoch"],
        "parameter_count": parameter_count(model),
        "dataset": metadata,
        "training": training,
        "evaluation_seconds_including_figures": perf_counter() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/full.json"))
    parser.add_argument("--checkpoint", type=Path, default=Path("models/best.pt"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--figures-dir", type=Path, default=Path("figures"))
    parser.add_argument("--output", type=Path, default=Path("reports/evaluation.json"))
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("--threads must be positive")
    setup_logging()
    torch.set_num_threads(args.threads)
    result = evaluate(
        args.checkpoint,
        read_config(args.config),
        args.data_dir,
        args.device,
        args.batch_size,
        args.figures_dir,
    )
    write_json(args.output, result)
    logging.info(
        "Surrogate RMSE %.6g; identity RMSE %.6g",
        result["surrogate"]["rmse"],
        result["identity_baseline"]["rmse"],
    )


if __name__ == "__main__":
    main()
