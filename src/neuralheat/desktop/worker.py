"""Frozen experiment worker: call existing scientific functions, never a shell."""

import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from .paths import DesktopPaths


def run_worker(paths: DesktopPaths, preset: str, output: Path) -> int:
    if preset not in {"smoke", "full"}:
        raise ValueError("Unsupported experiment preset")
    output = output.resolve()
    if output.parent != (paths.user / "runs/studio").resolve() or not re.fullmatch(
        r"\d{8}T\d{6}-[a-f0-9]{8}", output.name
    ):
        raise ValueError("Experiment output must be a managed user-data run directory")
    if not output.is_dir():
        raise FileNotFoundError("Experiment manager must create the run before starting its worker")
    paths.prepare()
    previous_stdout, previous_stderr = sys.stdout, sys.stderr
    with (output / "worker.log").open("a", encoding="utf-8", buffering=1) as stream:
        sys.stdout = sys.stderr = stream
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            stream=stream,
            force=True,
        )
        try:
            return run_pipeline(paths.assets, preset, output)
        except Exception:
            logging.exception("Experiment failed")
            return 1
        finally:
            logging.shutdown()
            sys.stdout, sys.stderr = previous_stdout, previous_stderr


def run_pipeline(assets: Path, preset: str, output: Path) -> int:
    """Use the same generator, training, evaluation and benchmark implementations."""
    import torch

    from neuralheat.benchmark import benchmark
    from neuralheat.common import read_config, write_json
    from neuralheat.dataset import generate, verify_cache
    from neuralheat.evaluate import evaluate
    from neuralheat.train import train

    config = read_config(assets / f"configs/{preset}.json")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # A runtime may be present without a usable driver/device. Probe before
    # allocating the training model; choose CPU if basic CUDA execution fails.
    if device == "cuda":
        try:
            torch.zeros(1, device="cuda").add_(1)
            torch.cuda.synchronize()
        except RuntimeError:
            logging.exception("CUDA probe failed; using CPU for this experiment")
            device = "cpu"
    reports, figures, models, data = [
        output / name for name in ("reports", "figures", "models", "data")
    ]
    reports.mkdir(parents=True, exist_ok=True)
    manifest = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "config": config,
        "device": device,
        "steps": [],
        "tests": "Not run inside release; release tests run during the build",
        "runner": "frozen worker calling original scientific implementations",
    }
    write_json(reports / "execution.json", manifest)

    def stage(name, action):
        logging.info("Running %s", name)
        started = perf_counter()
        # Retain the same per-stage log filenames as CLI runs, as well as SSE.
        handler = logging.FileHandler(reports / f"{name}.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logging.getLogger().addHandler(handler)
        try:
            result = action()
        except Exception:
            manifest["status"] = "failed"
            logging.exception("Stage %s failed", name)
            raise
        finally:
            logging.getLogger().removeHandler(handler)
            handler.close()
            manifest["steps"].append({"name": name, "wall_seconds": perf_counter() - started})
            write_json(reports / "execution.json", manifest)
        return result

    def data_stage():
        path, metadata = generate(config, data)
        verify_cache(path, metadata, checksums=True)

    stage("data", data_stage)
    stage("training", lambda: train(config, data, models, device, figures))
    evaluation = stage(
        "evaluation",
        lambda: evaluate(models / "best.pt", config, data, device, figures_dir=figures),
    )
    write_json(reports / "evaluation.json", evaluation)
    stage(
        "benchmark",
        lambda: benchmark(
            config, models / "best.pt", data, reports, figures, skip_cuda=device == "cpu"
        ),
    )
    manifest["status"] = "completed"
    write_json(reports / "execution.json", manifest)
    return 0
