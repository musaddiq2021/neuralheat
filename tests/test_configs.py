"""Configuration contracts can also be checked without scientific dependencies."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_full_dataset_contract() -> None:
    config = json.loads((ROOT / "configs/full.json").read_text())
    assert config["data"] == {"train": 2000, "validation": 300, "test": 300}
    assert config["benchmark"]["batch_sizes"] == [1, 16, 64]


def test_smoke_preserves_physics_and_is_separate() -> None:
    full = json.loads((ROOT / "configs/full.json").read_text())
    smoke = json.loads((ROOT / "configs/smoke.json").read_text())
    assert smoke["physics"] == full["physics"]
    assert smoke["seed"] != full["seed"]
    assert smoke["data"]["train"] < full["data"]["train"]
    assert smoke["data"]["test"] >= max(smoke["benchmark"]["batch_sizes"])
