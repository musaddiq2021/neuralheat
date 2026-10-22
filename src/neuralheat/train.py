"""MSE/Adam training with validation early stopping and atomic best checkpoints."""

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import torch
from torch import nn
from torch.utils.data import DataLoader

from .common import (
    file_sha256,
    read_config,
    resolve_device,
    seed_everything,
    setup_logging,
    write_json,
)
from .dataset import HeatDataset, generate, verify_cache
from .model import HeatUNet, parameter_count
from .visualization import plot_training


@dataclass
class EarlyStopping:
    patience: int
    min_delta: float
    best: float = float("inf")
    significant_best: float = float("inf")
    stale: int = 0

    def update(self, loss: float) -> bool:
        """Save every strict best; min_delta only controls patience resets."""
        improved = loss < self.best
        if improved:
            self.best = loss
        if loss < self.significant_best - self.min_delta:
            self.significant_best, self.stale = loss, 0
        else:
            self.stale += 1
        return improved

    @property
    def stopped(self) -> bool:
        return self.stale >= self.patience


def train(
    config: dict,
    data_dir: Path,
    output: Path,
    device_name: str = "auto",
    figures_dir: Path = Path("figures"),
) -> dict:
    settings = config["training"]
    if any(settings[key] < 1 for key in ("epochs", "batch_size", "patience", "threads")):
        raise ValueError("epochs, batch_size, patience and threads must be positive")
    if settings["learning_rate"] <= 0 or settings["min_delta"] < 0:
        raise ValueError("learning_rate must be positive and min_delta nonnegative")
    path, metadata = generate(config, data_dir)
    verify_cache(path, metadata, checksums=True)
    seed_everything(config["seed"])
    torch.set_num_threads(settings["threads"])
    device = resolve_device(device_name)
    scale = metadata["normalization_scale"]
    generator = torch.Generator().manual_seed(config["seed"])
    loaders = {
        split: DataLoader(
            HeatDataset(path, split, scale),
            batch_size=settings["batch_size"],
            shuffle=split == "train",
            generator=generator if split == "train" else None,
            num_workers=0,
        )
        for split in ("train", "validation")
    }
    model = HeatUNet(**config["model"]).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=settings["learning_rate"])
    criterion = nn.MSELoss()
    stopper = EarlyStopping(settings["patience"], settings["min_delta"])
    output.mkdir(parents=True, exist_ok=True)
    history: list[dict] = []
    best_epoch = 0
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    started = perf_counter()
    for epoch in range(1, settings["epochs"] + 1):
        losses = {}
        for split, loader in loaders.items():
            model.train(split == "train")
            total = 0.0
            with torch.set_grad_enabled(split == "train"):
                for initial, target in loader:
                    initial, target = initial.to(device), target.to(device)
                    if split == "train":
                        optimizer.zero_grad(set_to_none=True)
                    loss = criterion(model(initial), target)
                    if not torch.isfinite(loss):
                        raise RuntimeError("Nonfinite training loss; check configuration")
                    if split == "train":
                        loss.backward()
                        optimizer.step()
                    total += loss.item() * len(initial)
            losses[split] = total / len(loader.dataset)
        history.append({"epoch": epoch, **losses})
        logging.info(
            "epoch %d: train %.7g validation %.7g", epoch, losses["train"], losses["validation"]
        )
        if stopper.update(losses["validation"]):
            best_epoch = epoch
            checkpoint = {
                "format_version": 1,
                "model_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
                "config": config,
                "dataset_id": metadata["dataset_id"],
                "normalization_scale": scale,
                "epoch": epoch,
                "validation_mse_normalized": losses["validation"],
                "history": list(history),
                "torch_version": str(torch.__version__),
            }
            temporary = output / "best.pt.tmp"
            torch.save(checkpoint, temporary)
            temporary.replace(output / "best.pt")
        if stopper.stopped:
            logging.info("Early stopping after %d epochs", epoch)
            break
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    summary = {
        "config": config,
        "dataset_id": metadata["dataset_id"],
        "device": str(device),
        "epochs_executed": len(history),
        "best_epoch": best_epoch,
        "best_validation_mse_normalized": stopper.best,
        "training_seconds": perf_counter() - started,
        "parameter_count": parameter_count(model),
        "history": history,
        "checkpoint_sha256": file_sha256(output / "best.pt"),
        "training_timing_scope": "epoch loops including validation and checkpoint I/O; excludes data generation and model setup",
    }
    write_json(output / "training.json", summary)
    plot_training(history, figures_dir / "training_loss.png")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/full.json"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("models"))
    parser.add_argument("--figures-dir", type=Path, default=Path("figures"))
    parser.add_argument("--device", default="auto")
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--learning-rate", type=float)
    args = parser.parse_args()
    setup_logging()
    config = read_config(args.config)
    for argument, key in (
        (args.epochs, "epochs"),
        (args.batch_size, "batch_size"),
        (args.learning_rate, "learning_rate"),
    ):
        if argument is not None:
            config["training"][key] = argument
    train(config, args.data_dir, args.output, args.device, args.figures_dir)


if __name__ == "__main__":
    main()
