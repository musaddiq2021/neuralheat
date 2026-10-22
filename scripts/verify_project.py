"""Record static checks and pytest results without confusing skips with passes."""

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    reports = args.reports_dir.resolve()
    reports.mkdir(parents=True, exist_ok=True)
    junit = reports / "pytest.xml"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    commands = {
        "compile": ["-m", "compileall", "-q", "src", "tests", "scripts"],
        "lint": ["-m", "ruff", "check", "src", "tests", "scripts"],
        "format": ["-m", "ruff", "format", "--check", "src", "tests", "scripts"],
        "pytest": ["-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", "--junitxml", str(junit)],
    }
    results = []
    for name, arguments in commands.items():
        command = [sys.executable, *arguments]
        before = perf_counter()
        process = subprocess.run(
            command,
            cwd=repo,
            env=env,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        output = process.stdout + process.stderr
        (reports / f"verification_{name}.log").write_text(output, encoding="utf-8")
        results.append(
            {
                "name": name,
                "command": command,
                "return_code": process.returncode,
                "wall_seconds": perf_counter() - before,
            }
        )
        print(f"{name}: exit {process.returncode}\n{output}")
    summary = None
    if junit.exists():
        suites = ET.parse(junit).getroot().findall(".//testsuite")
        summary = {
            key: sum(int(suite.get(key, "0")) for suite in suites)
            for key in ("tests", "failures", "errors", "skipped")
        }
        summary["passed"] = (
            summary["tests"] - summary["failures"] - summary["errors"] - summary["skipped"]
        )
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "steps": results,
        "pytest": summary,
        "scientific_validation_complete": summary is not None
        and summary["skipped"] == 0
        and summary["errors"] == 0
        and summary["failures"] == 0,
        "note": "Skipped dependency modules do not validate their scientific or ML functionality. A CUDA-only skip may also occur on CPU hosts.",
    }
    (reports / "verification.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    sys.exit(0 if all(item["return_code"] == 0 for item in results) else 1)


if __name__ == "__main__":
    main()
