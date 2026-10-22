"""Run tests and the entire experiment, retaining logs and honest run status."""

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from check_environment import inspect_environment


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/full.json"))
    parser.add_argument("--output-root", type=Path, default=Path("."))
    parser.add_argument("--device", default="auto")
    parser.add_argument("--skip-cuda", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    root = args.output_root.resolve()
    config = args.config.resolve()
    reports, figures, models, data = [
        root / name for name in ("reports", "figures", "models", "data")
    ]
    reports.mkdir(parents=True, exist_ok=True)
    environment = inspect_environment()
    save(reports / "environment.json", environment)
    manifest = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "config": str(config),
        "status": "started",
        "steps": [],
        "environment": environment,
    }
    if not environment["ready"]:
        missing = [name for name, item in environment["packages"].items() if not item["available"]]
        manifest.update(status="blocked_missing_dependencies", missing=missing)
        save(reports / "execution.json", manifest)
        # Never overwrite an existing measured report with a blocked-run notice.
        if not (reports / "benchmark.json").exists():
            save(
                reports / "benchmark.json",
                {
                    "status": "not_run",
                    "reason": "Missing dependencies: " + ", ".join(missing),
                    "accuracy": None,
                    "latency": [],
                    "speedups": [],
                    "timestamp_utc": manifest["timestamp_utc"],
                },
            )
            with (reports / "benchmark.csv").open("w", encoding="utf-8", newline="") as handle:
                csv.writer(handle).writerow(
                    [
                        "method",
                        "device",
                        "scope",
                        "batch_size",
                        "warmup",
                        "repeats",
                        "median_ms",
                        "mean_ms",
                        "p95_ms",
                        "std_ms",
                        "throughput_samples_per_second",
                        "speedup",
                        "comparison",
                    ]
                )
            (reports / "benchmark.md").write_text(
                "# NEURALHEAT benchmark status\n\n**Not run.** Required dependencies could not be imported: "
                + ", ".join(missing)
                + ".\n\nNo accuracy, training, latency, speedup or throughput results exist for this run. No scientific figures or model checkpoints were generated. See execution.json and environment.json for the actual environment.\n",
                encoding="utf-8",
            )
        print("Experiment blocked by missing dependencies: " + ", ".join(missing), file=sys.stderr)
        sys.exit(1)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo / "src") + os.pathsep + env.get("PYTHONPATH", "")
    common = ["--config", str(config), "--data-dir", str(data)]
    commands = [] if args.skip_tests else [("tests", ["-m", "pytest", "-q", str(repo / "tests")])]
    commands += [
        ("data", ["-m", "neuralheat.dataset", *common, "--verify"]),
        (
            "training",
            [
                "-m",
                "neuralheat.train",
                *common,
                "--output",
                str(models),
                "--figures-dir",
                str(figures),
                "--device",
                args.device,
            ],
        ),
        (
            "evaluation",
            [
                "-m",
                "neuralheat.evaluate",
                *common,
                "--checkpoint",
                str(models / "best.pt"),
                "--output",
                str(reports / "evaluation.json"),
                "--figures-dir",
                str(figures),
                "--device",
                args.device,
            ],
        ),
        (
            "benchmark",
            [
                "-m",
                "neuralheat.benchmark",
                *common,
                "--checkpoint",
                str(models / "best.pt"),
                "--reports-dir",
                str(reports),
                "--figures-dir",
                str(figures),
                *(["--skip-cuda"] if args.skip_cuda else []),
            ],
        ),
    ]
    for name, arguments in commands:
        command = [sys.executable, *arguments]
        print(f"Running {name}", flush=True)
        started = perf_counter()
        with (reports / f"{name}.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                command,
                cwd=repo,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
            code = process.wait()
        manifest["steps"].append(
            {
                "name": name,
                "command": command,
                "return_code": code,
                "wall_seconds": perf_counter() - started,
            }
        )
        manifest["status"] = "failed" if code else "running"
        save(reports / "execution.json", manifest)
        if code:
            sys.exit(code)
    manifest["status"] = "completed"
    save(reports / "execution.json", manifest)


if __name__ == "__main__":
    main()
