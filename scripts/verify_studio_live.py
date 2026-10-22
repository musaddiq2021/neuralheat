"""Verify live Studio contracts against existing artifacts without training."""

import argparse
import json
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np

from neuralheat.common import file_sha256, write_json
from neuralheat.solver import SolverConfig, solve


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=Path("reports/studio/live-api.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]

    def fetch(path: str, body: dict | None = None):
        request = Request(
            args.base_url + "/api" + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    health = fetch("/health")
    assert health["application"] == "NEURALHEAT Studio"
    assert health["active_experiment"] is None, "Run live checks with the experiment worker idle"
    metadata = fetch("/model")
    assert metadata["available"]
    assert metadata["checkpoint_sha256"] == file_sha256(root / "models/best.pt")
    saved = json.loads((root / "reports/benchmark.json").read_text(encoding="utf-8"))
    assert fetch("/runs/primary")["benchmark"] == saved
    physics = SolverConfig(
        **{field.name: metadata["physics"][field.name] for field in fields(SolverConfig)}
    )
    simulation = fetch("/simulate", {"sample_index": 0, "frame_stride": 17})
    initial = np.asarray(simulation["initial"], dtype=np.float32)
    np.testing.assert_array_equal(simulation["frames"][-1]["field"], solve(initial, physics))
    assert simulation["prediction_valid_at_step"] == physics.steps
    assert all("prediction" not in frame for frame in simulation["frames"])
    prediction = fetch("/infer", {"sample_index": 0})
    np.testing.assert_array_equal(prediction["prediction"], simulation["prediction"])
    activation = fetch("/activations", {"node_id": "encoder2", "sample_index": 0})
    expected_shape = next(
        node["shape"] for node in metadata["graph"]["nodes"] if node["id"] == "encoder2"
    )
    assert activation["shape"] == expected_shape
    assert np.isfinite(np.asarray(activation["channels"])).all()
    assert fetch("/health")["active_experiment"] is None
    result = {
        "status": "passed",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "device": metadata["device"],
        "checkpoint_sha256": metadata["checkpoint_sha256"],
        "model_parameters": metadata["parameters"],
        "graph_tensor_nodes": len(metadata["graph"]["nodes"]),
        "graph_edges": len(metadata["graph"]["edges"]),
        "checks": [
            "existing checkpoint hash",
            "unaltered historical benchmark payload",
            "exact original solver final frame",
            "one final-time CNN prediction",
            "consistent infer/simulate outputs",
            "real activation tensor shape and finite values",
            "no experiment started",
        ],
        "training_started": False,
    }
    write_json(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
