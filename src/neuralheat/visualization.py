"""Noninteractive, standalone scientific figures; never synthesize measurements."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_training(history: list[dict], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    for key, label in (("train", "Training"), ("validation", "Validation")):
        ax.plot([row["epoch"] for row in history], [row[key] for row in history], label=label)
    ax.set(
        xlabel="Epoch",
        ylabel="MSE (normalized temperatures)",
        yscale="log",
        title="Training and validation loss",
    )
    ax.legend()
    ax.grid(alpha=0.25)
    _save(fig, path)


def plot_accuracy(
    initial: np.ndarray, reference: np.ndarray, predicted: np.ndarray, worst: int, path: Path
) -> None:
    # Show one deterministic sample and the hardest sample, without cherry-picking.
    indices = list(dict.fromkeys([0, worst]))
    fig, axes = plt.subplots(
        len(indices), 4, figsize=(14, 3.5 * len(indices)), squeeze=False, constrained_layout=True
    )
    for row, index in enumerate(indices):
        fields = [
            initial[index],
            reference[index],
            predicted[index],
            np.abs(predicted[index] - reference[index]),
        ]
        low = min(float(field.min()) for field in fields[:3])
        high = max(float(field.max()) for field in fields[:3])
        for col, (field, title) in enumerate(
            zip(
                fields,
                ["Initial temperature", "Numerical reference", "CNN prediction", "Absolute error"],
                strict=True,
            )
        ):
            ax = axes[row, col]
            options = {"vmin": low, "vmax": high} if col < 3 else {"vmin": 0}
            im = ax.imshow(
                field,
                origin="lower",
                extent=(0, 1, 0, 1),
                cmap="inferno" if col < 3 else "magma",
                **options,
            )
            ax.set(
                title=f"{title}\nTest sample {index}" + (" (worst RMSE)" if index == worst else ""),
                xlabel="x / L",
                ylabel="y / L",
            )
            fig.colorbar(im, ax=ax, shrink=0.75)
    _save(fig, path)


def plot_latency(rows: list[dict], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = sorted({row["method"] for row in rows})
    for label in labels:
        selected = sorted(
            [row for row in rows if row["method"] == label], key=lambda row: row["batch_size"]
        )
        ax.plot(
            [row["batch_size"] for row in selected],
            [row["median_ms"] for row in selected],
            marker="o",
            label=label,
        )
    ax.set(
        xlabel="Batch size",
        ylabel="Median batch latency (ms)",
        xscale="log",
        yscale="log",
        title="Measured latency: resident forward and end-to-end scopes",
    )
    ax.set_xticks([1, 16, 64], labels=["1", "16", "64"])
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    _save(fig, path)
