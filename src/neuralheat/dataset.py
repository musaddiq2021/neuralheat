"""Deterministic Gaussian-source datasets with content-addressed local caches."""

import argparse
import hashlib
import json
import logging
import platform
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

import numpy as np
import torch
from torch.utils.data import Dataset

from .common import file_sha256, fingerprint, read_config, setup_logging, write_json
from .solver import FloatArray, SolverConfig, solve, zero_boundary

SPLITS = ("train", "validation", "test")
GENERATOR_VERSION = 1
SOURCE_DISTRIBUTION = {
    "count_inclusive": [1, 5],
    "center_range": [0.12, 0.88],
    "amplitude_range": [0.4, 1.6],
    "sigma_range": [0.04, 0.16],
    "boundary": "zero edges after Gaussian summation",
}


def data_spec(config: dict) -> dict:
    """Only data-affecting settings belong in the cache identity."""
    return {
        "generator_version": GENERATOR_VERSION,
        "seed": config["seed"],
        "physics": asdict(SolverConfig(**config["physics"])),
        "counts": config["data"],
        "sources": SOURCE_DISTRIBUTION,
        "dtype": "float32",
        "normalization": "divide by training input maximum",
    }


def gaussian_initial(config: SolverConfig, rng: np.random.Generator) -> FloatArray:
    """Draw 1–5 nonnegative Gaussian sources on the physical square."""
    axis = np.linspace(0, config.length, config.grid_size, dtype=np.float32)
    xx, yy = np.meshgrid(axis, axis)
    field = np.zeros_like(xx)
    for _ in range(int(rng.integers(1, 6))):
        cx, cy = rng.uniform(0.12, 0.88, 2) * config.length
        amplitude = rng.uniform(0.4, 1.6)
        sigma = rng.uniform(0.04, 0.16) * config.length
        field += np.asarray(
            amplitude * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma**2)),
            dtype=np.float32,
        )
    zero_boundary(field)
    return field


def verify_cache(path: Path, metadata: dict, *, checksums: bool = False) -> None:
    """Validate shapes/dtypes; optionally verify complete file checksums."""
    size = metadata["spec"]["physics"]["grid_size"]
    for split, count in metadata["spec"]["counts"].items():
        for kind in ("inputs", "targets"):
            name = f"{split}_{kind}.npy"
            array = np.load(path / name, mmap_mode="r", allow_pickle=False)
            if array.shape != (count, size, size) or array.dtype != np.float32:
                raise ValueError(f"Invalid cache array: {name}; regenerate with --force")
            if checksums and file_sha256(path / name) != metadata["sha256"][name]:
                raise ValueError(f"Cache checksum mismatch: {name}; regenerate with --force")


def generate(config: dict, root: Path = Path("data"), *, force: bool = False) -> tuple[Path, dict]:
    """Generate or reuse a cache. Metadata is published only after completion.

    Each sample uses SeedSequence([root seed, split id, sample id]), so split
    streams are distinct and independent of chunking. No test data fit scaling.
    """
    spec = data_spec(config)
    counts = spec["counts"]
    if set(counts) != set(SPLITS) or any(not isinstance(n, int) or n < 1 for n in counts.values()):
        raise ValueError("train, validation and test counts must be positive integers")
    path = root / fingerprint(spec)
    metadata_path = path / "metadata.json"
    if metadata_path.exists() and not force:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata["spec"] != spec:
            raise ValueError("Cache specification mismatch")
        verify_cache(path, metadata)
        logging.info("Using data cache %s", path)
        return path, metadata
    path.mkdir(parents=True, exist_ok=True)
    metadata_path.unlink(missing_ok=True)
    physics = SolverConfig(**config["physics"])
    started = perf_counter()
    solver_seconds = 0.0
    checksums: dict[str, str] = {}
    sample_hashes: set[str] = set()
    scale = 0.0
    for split_id, split in enumerate(SPLITS):
        count = counts[split]
        shape = (count, physics.grid_size, physics.grid_size)
        inputs = np.lib.format.open_memmap(
            path / f"{split}_inputs.npy", mode="w+", dtype=np.float32, shape=shape
        )
        targets = np.lib.format.open_memmap(
            path / f"{split}_targets.npy", mode="w+", dtype=np.float32, shape=shape
        )
        for start in range(0, count, 64):
            stop = min(start + 64, count)
            batch = np.stack(
                [
                    gaussian_initial(
                        physics,
                        np.random.default_rng(
                            np.random.SeedSequence([config["seed"], split_id, index])
                        ),
                    )
                    for index in range(start, stop)
                ]
            )
            # Detect accidental duplicates across all splits, rather than assume disjointness.
            for field in batch:
                digest = hashlib.sha256(field.tobytes()).hexdigest()
                if digest in sample_hashes:
                    raise ValueError("Duplicate initial field across dataset; change seed")
                sample_hashes.add(digest)
            inputs[start:stop] = batch
            before = perf_counter()
            solution = solve(batch, physics)
            solver_seconds += perf_counter() - before
            targets[start:stop] = solution
            if split == "train":
                scale = max(scale, float(batch.max()))
        inputs.flush()
        targets.flush()
        del inputs, targets
        for kind in ("inputs", "targets"):
            name = f"{split}_{kind}.npy"
            checksums[name] = file_sha256(path / name)
        logging.info("Generated %s: %d fields", split, count)
    metadata = {
        "spec": spec,
        "dataset_id": fingerprint(spec),
        "normalization_scale": scale,
        "generation_seconds": perf_counter() - started,
        "solver_seconds": solver_seconds,
        "sha256": checksums,
        "unique_input_count": len(sample_hashes),
        "numpy_version": str(np.__version__),
        "python_version": platform.python_version(),
        "numerical": physics.metadata(),
    }
    write_json(metadata_path, metadata)
    return path, metadata


class HeatDataset(Dataset):
    """Read-only float32 cache; return normalized 1-channel tensor copies."""

    def __init__(self, path: Path, split: str, scale: float):
        if split not in SPLITS or not np.isfinite(scale) or scale <= 0:
            raise ValueError("Invalid split or normalization scale")
        self.inputs = np.load(path / f"{split}_inputs.npy", mmap_mode="r")
        self.targets = np.load(path / f"{split}_targets.npy", mmap_mode="r")
        self.scale = scale

    def __len__(self) -> int:
        return len(self.inputs)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        return (
            torch.from_numpy(np.array(self.inputs[index], copy=True)[None] / self.scale),
            torch.from_numpy(np.array(self.targets[index], copy=True)[None] / self.scale),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/full.json"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--verify", action="store_true", help="Verify all cached file SHA256 checksums"
    )
    args = parser.parse_args()
    setup_logging()
    path, metadata = generate(read_config(args.config), args.data_dir, force=args.force)
    if args.verify:
        verify_cache(path, metadata, checksums=True)
    logging.info(
        "Dataset %s; scale=%.6f; generation=%.3fs",
        path,
        metadata["normalization_scale"],
        metadata["generation_seconds"],
    )


if __name__ == "__main__":
    main()
