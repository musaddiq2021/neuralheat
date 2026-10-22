"""Trace PE dependencies and build a controlled, separate one-DLL exclusion experiment.

Never edits a source bundle, environment, release pointer or scientific artifact.
The experimental payload reuses the verified frozen executable byte for byte;
it is an exclusion experiment, not a newly compiled application release.
"""

import argparse
import ast
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pefile

TARGET = "cusolverMg64_11.dll"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024**2), b""):
            value.update(block)
    return value.hexdigest()


def pe_dependencies(path: Path) -> dict:
    """Inspect ordinary and delay-load imports without loading any target DLL."""
    with pefile.PE(str(path), fast_load=True) as image:
        image.parse_data_directories(
            directories=[
                pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"],
            ]
        )
        return {
            kind: [entry.dll.decode("ascii", errors="replace") for entry in getattr(image, field, [])]
            for kind, field in (
                ("imports", "DIRECTORY_ENTRY_IMPORT"),
                ("delay_imports", "DIRECTORY_ENTRY_DELAY_IMPORT"),
            )
        }


def investigate(root: Path, source: Path, toc: Path, output: Path, experiment: Path | None) -> dict:
    source = source.resolve()
    target = source / "_internal/torch/lib" / TARGET
    if not target.is_file():
        raise FileNotFoundError(target)
    if output.exists():
        raise FileExistsError(f"Use a fresh evidence directory: {output}")
    output.mkdir(parents=True)
    rows = ast.literal_eval(toc.read_text(encoding="utf-8"))[0]
    origins = {name.replace("\\", "/"): Path(origin) for name, origin, _ in rows}
    selected = [
        "_internal/msvcp140.dll",
        "_internal/vcruntime140.dll",
        "_internal/vcruntime140_1.dll",
        "_internal/numpy.libs/msvcp140-a4c2229bdc2a2a630acdc095b4d86008.dll",
        f"_internal/torch/lib/{TARGET}",
    ]
    provenance = []
    for name in selected:
        current = source / name
        origin = origins[name.removeprefix("_internal/")]
        provenance.append(
            {
                "bundled_file": name,
                "bundled_bytes": current.stat().st_size,
                "bundled_sha256": digest(current),
                "recorded_collection_source": str(origin),
                "source_present": origin.is_file(),
                "current_source_sha256": digest(origin) if origin.is_file() else None,
            }
        )
    dependencies, referrers, failures = {}, [], []
    for path in sorted(source.rglob("*")):
        if path.suffix.lower() not in {".exe", ".dll", ".pyd"}:
            continue
        try:
            row = pe_dependencies(path)
        except pefile.PEFormatError as exc:
            failures.append({"file": path.relative_to(source).as_posix(), "error": str(exc)})
            continue
        name = path.relative_to(source).as_posix()
        dependencies[name] = row
        if TARGET.lower() in {dep.lower() for deps in row.values() for dep in deps}:
            referrers.append(name)
    (output / "pe-imports.json").write_text(json.dumps(dependencies, indent=2) + "\n")
    result = {
        "source_bundle": str(source),
        "source_toc": str(toc),
        "target": TARGET,
        "provenance": provenance,
        "pe_files_inspected": len(dependencies),
        "pe_parse_failures": failures,
        "target_static_or_delay_importers": referrers,
        "dynamic_load_limitation": "PE imports cannot rule out LoadLibrary by name; frozen runtime tests are required",
    }
    if experiment is not None:
        destination = experiment.resolve()
        if destination.exists() or destination == source or destination.is_relative_to(source):
            raise ValueError("A fresh destination outside the original bundle is required")
        destination.mkdir(parents=True)
        copied, omitted = [], []
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            name = path.relative_to(source)
            if path == target:
                omitted.append(name.as_posix())
                continue
            target_path = destination / name
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target_path)
            original_hash = digest(path)
            if digest(target_path) != original_hash:
                raise RuntimeError(f"Experimental copy differs: {name}")
            copied.append({"path": name.as_posix(), "sha256": original_hash, "bytes": path.stat().st_size})
        if omitted != [f"_internal/torch/lib/{TARGET}"]:
            raise AssertionError(f"Unexpected omission set: {omitted}")
        result["experiment"] = {
            "executable": str(destination / "NeuralHeat Studio.exe"),
            "omitted": omitted,
            "identical_copied_files": len(copied),
            "bytes": sum(row["bytes"] for row in copied),
            "copy_manifest": "experimental-copy.json",
            "promoted": False,
        }
        (output / "experimental-copy.json").write_text(json.dumps(copied, indent=2) + "\n")
    (output / "investigation.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--toc", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--create-experiment", action="store_true")
    args = parser.parse_args()
    latest = json.loads((root / "dist/desktop/latest.json").read_text(encoding="utf-8-sig"))
    source = args.source or Path(latest["executable"]).parent
    toc = args.toc or root / "build/desktop" / latest["build_id"] / "pyinstaller/NeuralHeat Studio/COLLECT-00.toc"
    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    output = args.output or root / "reports/redistribution" / run_id
    experiment = root / "dist/experiments" / run_id / "NeuralHeat Studio" if args.create_experiment else None
    result = investigate(root, source, toc, output, experiment)
    print(json.dumps({key: value for key, value in result.items() if key != "provenance"}, indent=2))
