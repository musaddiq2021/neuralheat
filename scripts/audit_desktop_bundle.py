"""Measure a frozen release without changing it, retaining a preservation manifest."""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def embedded_modules(executable: Path) -> dict:
    from PyInstaller.archive.readers import CArchiveReader

    archive = CArchiveReader(str(executable)).open_embedded_archive("PYZ.pyz")
    families = defaultdict(int)
    for name, entry in archive.toc.items():
        families[name.split(".")[0]] += entry[2]
    return {
        "modules": len(archive.toc),
        "family_compressed_bytes": dict(
            sorted(families.items(), key=lambda item: item[1], reverse=True)
        ),
        "test_module_compressed_bytes": sum(
            entry[2]
            for name, entry in archive.toc.items()
            if name.startswith(("torch.testing._internal", "torch.fx.passes.tests", "_pytest"))
        ),
    }


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024**2), b""):
            result.update(chunk)
    return result.hexdigest()


def audit(bundle: Path, output: Path) -> dict:
    bundle = bundle.resolve(strict=True)
    if not (bundle / "NeuralHeat Studio.exe").is_file():
        raise FileNotFoundError("Expected a NeuralHeat Studio onedir release")
    files = []
    groups = defaultdict(int)
    by_size = defaultdict(list)
    for path in sorted(bundle.rglob("*")):
        if path.is_file():
            relative = path.relative_to(bundle).as_posix()
            size = path.stat().st_size
            row = {"path": relative, "bytes": size, "sha256": digest(path)}
            files.append(row)
            by_size[size].append(row)
            parts = Path(relative).parts
            group = "/".join(parts[:2]) if parts[0] == "_internal" else parts[0]
            groups[group] += size
    duplicates = []
    for size, rows in by_size.items():
        if len(rows) < 2 or size == 0:
            continue
        hashes = defaultdict(list)
        for row in rows:
            hashes[row["sha256"]].append(row["path"])
        duplicates += [
            {
                "bytes_each": size,
                "redundant_bytes": size * (len(paths) - 1),
                "sha256": sha,
                "paths": paths,
            }
            for sha, paths in hashes.items()
            if len(paths) > 1
        ]
    result = {
        "bundle": str(bundle),
        "files": files,
        "file_count": len(files),
        "uncompressed_bytes": sum(row["bytes"] for row in files),
        "groups": dict(sorted(groups.items(), key=lambda item: item[1], reverse=True)),
        "largest_files": sorted(files, key=lambda row: row["bytes"], reverse=True)[:40],
        "duplicate_groups": sorted(
            duplicates, key=lambda row: row["redundant_bytes"], reverse=True
        ),
        "duplicate_redundant_bytes": sum(item["redundant_bytes"] for item in duplicates),
    }
    try:
        result["embedded_python"] = embedded_modules(bundle / "NeuralHeat Studio.exe")
    except (ImportError, ValueError, KeyError, RuntimeError):
        result["embedded_python"] = None
    output.mkdir(parents=True, exist_ok=True)
    (output / "bundle-audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with (output / "bundle-files.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["path", "bytes", "sha256"])
        writer.writeheader()
        writer.writerows(files)
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in {"files", "largest_files", "duplicate_groups"}
            },
            indent=2,
        )
    )
    print("Largest files:")
    for row in result["largest_files"][:20]:
        print(f"{row['bytes'] / 1024**2:9.2f} MiB  {row['path']}")
    print("Largest duplicate groups:")
    for row in result["duplicate_groups"][:15]:
        print(f"{row['redundant_bytes'] / 1024**2:9.2f} MiB redundant  {row['paths']}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    bundle = (
        args.bundle
        or Path(
            json.loads((root / "dist/desktop/latest.json").read_text(encoding="utf-8-sig"))[
                "executable"
            ]
        ).parent
    )
    audit(bundle, args.output)
