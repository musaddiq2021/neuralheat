"""Shared configuration, provenance, and reproducibility helpers."""

import hashlib
import json
import logging
import os
import random
from pathlib import Path
from typing import Any

import numpy as np
import torch


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def read_config(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    """Atomically publish JSON, rejecting nonstandard NaN/Infinity values."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def fingerprint(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


def file_sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def seed_everything(seed: int) -> None:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False


def resolve_device(requested: str = "auto") -> torch.device:
    device = (
        torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if requested == "auto"
        else torch.device(requested)
    )
    if device.type not in ("cpu", "cuda"):
        raise ValueError("Supported devices are auto, cpu, cuda, cuda:N")
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable in this PyTorch installation")
    return device
