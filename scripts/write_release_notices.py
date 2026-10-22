"""Retain dependency license texts and build-environment attribution in a release."""

import argparse
import importlib.metadata
import re
import shutil
import sys
from pathlib import Path


def write_notices(destination: Path) -> None:
    licenses = destination / "third-party-licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    lines = [
        "NeuralHeat Studio third-party notices",
        "License evidence from the recorded build environment (including build tools).",
        "See python-environment.txt in the build reports for exact versions.",
        "",
    ]
    for distribution in sorted(
        importlib.metadata.distributions(), key=lambda d: d.metadata["Name"]
    ):
        name = distribution.metadata["Name"]
        folder = licenses / re.sub(r"[^a-zA-Z0-9_.-]", "_", name)
        copied = []
        for entry in distribution.files or []:
            if not any(term in entry.name.lower() for term in ("license", "copying", "notice")):
                continue
            source = Path(distribution.locate_file(entry))
            if source.is_file():
                folder.mkdir(exist_ok=True)
                target = folder / f"{len(copied):02d}-{source.name}"
                shutil.copy2(source, target)
                copied.append(target.relative_to(destination).as_posix())
        declared = distribution.metadata.get("License-Expression") or distribution.metadata.get(
            "License", "See upstream metadata"
        )
        lines += [f"{name} {distribution.version}", str(declared), *copied, ""]
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        shutil.copy2(python_license, licenses / "Python-LICENSE.txt")
    (destination / "THIRD_PARTY_NOTICES.txt").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path)
    write_notices(parser.parse_args().destination)
