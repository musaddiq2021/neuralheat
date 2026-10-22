"""Real checkpoint integration plus controlled process-lifecycle tests.

No new full/smoke experiment is launched by these tests. Existing CLI tests
remain unchanged; their small training round-trip is independent of Studio.
"""

import asyncio
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
np = pytest.importorskip("numpy")
torch = pytest.importorskip("torch")
from fastapi.testclient import TestClient

from neuralheat.evaluate import predict
from neuralheat.solver import solve
from neuralheat.studio.app import create_app
from neuralheat.studio.experiments import ExperimentManager, WindowsJob
from neuralheat.studio.schemas import FieldRequest, SimulationRequest
from neuralheat.studio.service import StudioService

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client():
    if not (ROOT / "models/best.pt").exists():
        pytest.skip("Saved reference checkpoint required for Studio integration tests")
    with TestClient(create_app(ROOT, "cpu")) as test_client:
        yield test_client


def test_metadata_is_the_loaded_model_with_real_hook_shapes(client):
    response = client.get("/api/model")
    assert response.status_code == 200
    payload = response.json()
    assert payload["parameters"] == 29617
    assert payload["fixed_final_time_only"]
    graph = payload["graph"]
    nodes = {node["id"]: node for node in graph["nodes"]}
    assert nodes["encoder1"]["shape"] == [1, 8, 64, 64]
    assert nodes["bottleneck"]["shape"] == [1, 32, 16, 16]
    assert nodes["encoder1"]["children"][0]["shape"] == [1, 8, 64, 64]
    assert any(
        edge["source"] == "encoder1" and edge["target"] == "cat_1" for edge in graph["edges"]
    )


def test_reports_and_history_are_returned_without_recomputation(client):
    expected = json.loads((ROOT / "reports/benchmark.json").read_text())
    payload = client.get("/api/runs/primary").json()
    assert payload["benchmark"] == expected
    assert payload["training"] == expected["accuracy"]["training"]
    assert client.get("/api/training").json()["training"] == payload["training"]
    assert client.get("/api/runs/not-a-run").status_code == 404
    assert client.get("/api/runs/primary/logs?kind=training").json()["lines"]
    assert client.get("/api/runs/primary/logs?kind=../../models/best.pt").status_code == 422


def test_simulation_frames_match_existing_solver_and_only_one_final_prediction(client):
    request = {
        "sources": [{"x": 0.4, "y": 0.6, "sigma": 0.08, "amplitude": 1.2}],
        "frame_stride": 7,
    }
    payload = client.post("/api/simulate", json=request).json()
    initial = np.array(payload["initial"], dtype=np.float32)
    service = client.app.state.service
    expected = solve(initial, service.physics)
    np.testing.assert_array_equal(payload["frames"][-1]["field"], expected)
    assert payload["frames"][-1]["step"] == service.physics.steps
    assert payload["prediction_valid_at_step"] == service.physics.steps
    assert all("prediction" not in frame for frame in payload["frames"])
    np.testing.assert_allclose(
        payload["absolute_error"],
        np.abs(np.asarray(payload["prediction"], dtype=np.float32) - expected),
        atol=1e-8,
    )
    assert initial[0].sum() == 0


def test_inference_reuses_checkpoint_and_preserves_original_normalization(client):
    service = client.app.state.service
    identity = id(service.model)
    request = FieldRequest(sample_index=0)
    initial, _ = service.initial(request)
    with torch.inference_mode():
        expected = predict(
            service.model, initial[None], service.checkpoint["normalization_scale"], service.device
        )[0]
    payload = client.post("/api/infer", json={"sample_index": 0}).json()
    np.testing.assert_array_equal(payload["prediction"], expected)
    client.post("/api/infer", json={"sample_index": 1})
    assert id(service.model) == identity


def test_activations_equal_an_independent_forward_hook(client):
    service = client.app.state.service
    initial, _ = service.initial(FieldRequest(sample_index=0))
    captured = {}
    handle = service.model.encoder1.register_forward_hook(
        lambda _m, _a, output: captured.__setitem__("value", output.detach().cpu().numpy().copy())
    )
    try:
        with torch.inference_mode():
            predict(
                service.model,
                initial[None],
                service.checkpoint["normalization_scale"],
                service.device,
            )
    finally:
        handle.remove()
    payload = client.post(
        "/api/activations", json={"node_id": "encoder1", "sample_index": 0}
    ).json()
    np.testing.assert_array_equal(payload["channels"], captured["value"][0])
    assert "encoder1.0" in payload["module_hooks"]
    assert (
        client.post(
            "/api/activations", json={"node_id": "fake_layer", "sample_index": 0}
        ).status_code
        == 400
    )
    assert len(service.model.encoder1._forward_hooks) == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"sources": [{"x": 2, "y": 0.5}]},
        {"sample_index": -1},
        {"sources": [{"x": 0.2, "y": 0.3, "amplitude": float("inf")}]},
        {"sources": [{"x": 0.2, "y": 0.3}], "sample_index": 0},
    ],
)
def test_invalid_inputs_rejected(client, payload):
    # Infinity cannot be transported as standard JSON; validate it at the schema.
    if "Infinity" in json.dumps(payload):
        with pytest.raises(ValueError):
            SimulationRequest.model_validate(payload)
    else:
        assert client.post("/api/simulate", json=payload).status_code == 422


def test_no_training_on_open_and_no_arbitrary_commands_or_remote_origins(client):
    assert client.get("/api/health").json()["active_experiment"] is None
    assert client.post("/api/experiments", json={"preset": "cmd.exe"}).status_code == 422
    assert (
        client.post("/api/experiments", json={"preset": "smoke", "command": "whoami"}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/experiments",
            json={"preset": "smoke"},
            headers={"Origin": "https://foreign.example"},
        ).status_code
        == 403
    )
    assert client.get("/api/health", headers={"Host": "foreign.example"}).status_code == 400
    assert client.get("/api/experiments/unknown/events").status_code == 404


def test_cpu_fallback_without_checkpoint_does_not_generate_data(tmp_path):
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/full.json").write_text((ROOT / "configs/full.json").read_text())
    service = StudioService(tmp_path, "cpu")
    result = service.simulate(SimulationRequest(sources=[], frame_stride=120))
    assert result["prediction"] is None
    assert np.count_nonzero(result["frames"][-1]["field"]) == 0
    assert not (tmp_path / "data").exists()


def test_historical_report_never_borrows_a_different_checkpoint_history(tmp_path):
    for name in ("configs", "models", "reports"):
        (tmp_path / name).mkdir()
    (tmp_path / "configs/full.json").write_text((ROOT / "configs/full.json").read_text())
    (tmp_path / "reports/benchmark.json").write_text(
        json.dumps(
            {"status": "completed", "accuracy": {"checkpoint_sha256": "historical-checkpoint"}}
        )
    )
    (tmp_path / "models/training.json").write_text(
        json.dumps({"checkpoint_sha256": "different-checkpoint", "history": [{"epoch": 99}]})
    )
    service = StudioService(tmp_path, "cpu")
    payload = service.run("primary")
    assert payload["training"] is None
    assert "matches" in payload["training_note"]


def test_allowlisted_process_lifecycle_and_sse_replay(tmp_path, monkeypatch):
    # A harmless fake worker exercises start/stream/cancel with no training.
    import neuralheat.studio.experiments as module

    exited = threading.Event()
    invocations = []

    class Lines:
        def __iter__(self):
            yield "epoch 1: train 0.001 validation 0.002\n"
            exited.wait(3)

    class Process:
        stdout = Lines()
        pid = 123

        def __init__(self, command, **kwargs):
            invocations.append((command, kwargs))

        def wait(self, timeout=None):
            exited.wait(3)
            return 1

        def terminate(self):
            exited.set()

        def kill(self):
            exited.set()

    class Job:
        def __init__(self, _process):
            pass

        def close(self):
            exited.set()

    monkeypatch.setattr(module.subprocess, "Popen", Process)
    monkeypatch.setattr(module, "WindowsJob", Job)
    monkeypatch.setattr(module.os, "killpg", lambda *_: exited.set(), raising=False)
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/smoke.json").write_text(json.dumps({"training": {"epochs": 3}}))
    manager = ExperimentManager(tmp_path)
    with pytest.raises(ValueError):
        manager.start("shell")
    record = manager.start("smoke")
    with pytest.raises(ValueError, match="already running"):
        manager.start("full")
    for _ in range(50):
        if manager.records[record["id"]]["epoch"]:
            break
        time.sleep(0.01)
    assert manager.records[record["id"]]["history"][0]["validation"] == 0.002
    manager.cancel(record["id"])
    for _ in range(50):
        if manager.active is None:
            break
        time.sleep(0.01)
    assert manager.history()[0]["status"] == "cancelled"
    events = manager.log_events(record["id"], 0)
    assert any(event["event"] == "epoch" for event in events)
    assert events[0]["data"]["history"] == []  # Initial state did not mutate with live history.
    command, kwargs = invocations[0]
    assert command[0] == sys.executable
    assert "shell" not in kwargs
    assert str(tmp_path / "configs/smoke.json") in command
    assert str(tmp_path / "runs/studio" / record["id"]) in command

    async def consume():
        return [chunk async for chunk in manager.stream(record["id"], after=1)]

    chunks = asyncio.run(consume())
    assert any("event: epoch" in chunk for chunk in chunks)
    assert chunks[-1] == "event: end\ndata: {}\n\n"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process-tree containment")
def test_windows_job_terminates_owned_process():
    try:
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except PermissionError:
        pytest.skip(
            "Current sandbox forbids child processes; verify job containment in a normal local shell"
        )
    before = time.monotonic()
    job = WindowsJob(process)
    job.close()
    process.wait(timeout=5)
    assert time.monotonic() - before < 5
    assert process.poll() is not None
