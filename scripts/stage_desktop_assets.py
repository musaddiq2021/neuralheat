"""Copy a verified scientific snapshot to a new staging directory; never mutate inputs."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def asset_files(root: Path) -> list[Path]:
    """Ship the saved checkpoint, its complete cached dataset and historical runs."""
    import torch

    from neuralheat.dataset import verify_cache

    checkpoint = torch.load(root / "models/best.pt", map_location="cpu", weights_only=True)
    dataset = checkpoint["dataset_id"]
    if not isinstance(dataset, str) or not dataset.isalnum():
        raise ValueError("Invalid checkpoint dataset identifier")
    required = [
        root / name
        for name in (
            "models/best.pt",
            "models/training.json",
            "configs/full.json",
            "configs/smoke.json",
            "reports/benchmark.json",
            "frontend/dist/index.html",
            "desktop/neuralheat.ico",
        )
    ]
    data = root / "data" / dataset
    required += [data / "metadata.json"]
    required += [
        data / f"{split}_{kind}.npy"
        for split in ("train", "validation", "test")
        for kind in ("inputs", "targets")
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Required release asset missing: {path}")
    verify_cache(
        data, json.loads((data / "metadata.json").read_text(encoding="utf-8")), checksums=True
    )
    expected = json.loads((root / "models/training.json").read_text(encoding="utf-8"))
    if (
        expected["checkpoint_sha256"]
        != hashlib.sha256((root / "models/best.pt").read_bytes()).hexdigest()
    ):
        raise ValueError("Saved training history does not match the release checkpoint")
    paths = set(required)
    for directory in (root / "frontend/dist", data, root / "desktop"):
        paths.update(path for path in directory.rglob("*") if path.is_file())
    for directory in (root / "reports", root / "figures"):
        paths.update(
            path for path in directory.glob("*") if path.is_file() and path.name != ".gitkeep"
        )
    # Archive saved run reports/history/figures, not duplicate training caches.
    runs = root / "runs"
    if runs.exists():
        for report in runs.rglob("reports/benchmark.json"):
            run = report.parent.parent
            for name in ("reports", "figures"):
                paths.update(path for path in (run / name).rglob("*") if path.is_file())
            history = run / "models/training.json"
            if history.is_file():
                paths.add(history)
    for path in paths:
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Asset escaped project tree: {path}")
    return sorted(paths)


def stage(root: Path, destination: Path) -> dict:
    root, destination = root.resolve(), destination.resolve()
    if destination.exists():
        raise FileExistsError(
            "Release staging must use a new directory; existing assets are never replaced"
        )
    files = asset_files(root)
    destination.mkdir(parents=True)
    hashes = {}
    total = 0
    for source in files:
        name = source.relative_to(root).as_posix()
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise OSError(f"Staged asset checksum mismatch: {name}")
        hashes[name] = digest
        total += target.stat().st_size
    manifest = {"format_version": 1, "sha256": hashes, "bytes": total}
    (destination / "asset-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def verify_sources(root: Path, manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, expected in manifest["sha256"].items():
        path = root / name
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Manifest contains an invalid source path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise OSError(f"Original asset changed during release build: {name}")
    print(f"All {len(manifest['sha256'])} original assets remain unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--destination", type=Path)
    action.add_argument("--verify-manifest", type=Path)
    args = parser.parse_args()
    if args.verify_manifest:
        verify_sources(args.root, args.verify_manifest)
    else:
        result = stage(args.root, args.destination)
        print(
            f"Staged {len(result['sha256'])} verified assets ({result['bytes'] / 1024**2:.1f} MiB)"
        )
