"""Inspect a runtime without importing any project or scientific dependencies."""

import argparse
import importlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def inspect_environment() -> dict:
    packages = {}
    for name in ("numpy", "torch", "matplotlib", "pytest"):
        try:
            module = importlib.import_module(name)
            packages[name] = {"available": True, "version": str(module.__version__)}
        except Exception as error:
            packages[name] = {"available": False, "error": f"{type(error).__name__}: {error}"}
    try:
        gpu = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        gpu_info = gpu.stdout.strip() if gpu.returncode == 0 else gpu.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        gpu_info = str(error)
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "packages": packages,
        "nvidia_smi": gpu_info,
        "installed_distributions": sorted(
            f"{item.metadata['Name']}=={item.version}"
            for item in importlib.metadata.distributions()
        ),
        "ready": all(item["available"] for item in packages.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("reports/environment.json"))
    args = parser.parse_args()
    result = inspect_environment()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ready"] else 1)


if __name__ == "__main__":
    main()
