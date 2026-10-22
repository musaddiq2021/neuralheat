"""Desktop asset isolation, authenticated dynamic ports and frozen worker contracts."""

import json
import socket
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from neuralheat.desktop.paths import DesktopPaths, WorkspaceLock
from neuralheat.desktop.server import DesktopServer
from neuralheat.desktop.verification import port_closed
from neuralheat.desktop.worker import run_worker
from neuralheat.studio.app import create_app
from neuralheat.studio.experiments import ExperimentManager

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native single-workspace mutex")
def test_only_one_desktop_owns_a_workspace_and_lock_is_released(tmp_path):
    first = WorkspaceLock(tmp_path)
    try:
        with pytest.raises(RuntimeError, match="already running"):
            WorkspaceLock(tmp_path)
    finally:
        first.close()
    second = WorkspaceLock(tmp_path)
    second.close()


def test_user_state_and_settings_never_write_into_assets(tmp_path, monkeypatch):
    paths = DesktopPaths(tmp_path / "assets", tmp_path / "user")
    paths.assets.mkdir()
    with monkeypatch.context() as context:
        for name in ("MPLCONFIGDIR", "TORCH_HOME", "XDG_CACHE_HOME", "MPLBACKEND"):
            context.setenv(name, "previous")
        paths.prepare()
        assert (paths.user / "runs/studio").is_dir()
        paths.save_window(1400, 900)
        assert paths.load_window() == {"width": 1400, "height": 900}
        (paths.user / "settings/window.json").write_text("corrupt")
        assert paths.load_window() == {"width": 1480, "height": 980}
        assert not list(paths.assets.iterdir())
    with pytest.raises(ValueError, match="outside"):
        DesktopPaths(paths.assets, paths.assets / "state").prepare()


def test_asset_validation_does_not_silently_run_without_built_frontend(tmp_path):
    paths = DesktopPaths(tmp_path, tmp_path.parent / "user")
    with pytest.raises(FileNotFoundError, match="frontend/dist/index.html"):
        paths.validate_assets()


def test_ephemeral_socket_is_reserved_without_using_development_ports(tmp_path):
    first = DesktopServer(ROOT, tmp_path)
    second = DesktopServer(ROOT, tmp_path)
    try:
        assert first.port != second.port
        assert first.socket.getsockname()[0] == "127.0.0.1"
        with socket.socket() as collision:
            with pytest.raises(OSError):
                collision.bind(("127.0.0.1", first.port))
    finally:
        first.stop()
        second.stop()
    assert port_closed(first.port)


def test_desktop_session_requires_cookie_and_exact_dynamic_origin(tmp_path):
    origin = "http://127.0.0.1:49172"
    app = create_app(ROOT, "cpu", user_root=tmp_path, desktop_origin=origin, session_token="secret")
    with TestClient(app, base_url=origin) as client:
        assert client.get("/api/health").status_code == 401
        assert client.get("/desktop-session/wrong").status_code == 401
        response = client.get("/desktop-session/secret", follow_redirects=False)
        assert response.status_code == 303
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        assert client.get("/api/health", headers={"Origin": origin}).json()["mode"] == "desktop"
        assert (
            client.post(
                "/api/infer", json={"sample_index": 0}, headers={"Origin": origin}
            ).status_code
            == 200
        )
        assert (
            client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"}).status_code
            == 403
        )
        assert app.state.experiments.directory == tmp_path / "runs/studio"
        assert app.state.service.checkpoint_path == ROOT / "models/best.pt"
        history = tmp_path / "runs/studio/archived/reports"
        history.mkdir(parents=True)
        (history / "benchmark.json").write_text(json.dumps({"status": "completed"}))
        runs = client.get("/api/runs").json()
        user_run = next(item for item in runs if item["relative_path"].startswith("user/"))
        assert (
            client.get(f"/api/runs/{user_run['id']}").json()["benchmark"]["status"] == "completed"
        )
        assert client.get("/api/health").json()["active_experiment"] is None


def test_dynamic_backend_serves_real_model_and_stops_its_port(tmp_path):
    import httpx

    server = DesktopServer(ROOT, tmp_path, "cpu")
    try:
        server.start(timeout=30)
        with httpx.Client(trust_env=False, timeout=30) as client:
            assert client.get(server.entry_url).status_code == 303
            assert client.get(server.origin + "/api/health").json()["device"] == "cpu"
            model = client.get(server.origin + "/api/model").json()
            assert len(model["graph"]["nodes"]) == 17
            prediction = client.post(server.origin + "/api/infer", json={"sample_index": 0}).json()
            assert len(prediction["prediction"]) == 64
    finally:
        server.stop()
    assert not server.thread.is_alive()
    assert port_closed(server.port)


def test_frozen_worker_dispatch_uses_executable_and_user_output(tmp_path, monkeypatch):
    import neuralheat.studio.experiments as module

    commands = []

    class Process:
        stdout = []

        def __init__(self, command, **kwargs):
            commands.append((command, kwargs))
            output = Path(command[command.index("--output-root") + 1])
            (output / "worker.log").write_text("epoch 1: train 0.001 validation 0.002\n")

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

    class Job:
        def __init__(self, _process):
            pass

        def close(self):
            pass

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(module.subprocess, "Popen", Process)
    monkeypatch.setattr(module, "WindowsJob", Job)
    manager = ExperimentManager(ROOT, work_root=tmp_path)
    record = manager.start("smoke")
    deadline = time.monotonic() + 3
    while manager.active and time.monotonic() < deadline:
        time.sleep(0.01)
    command, kwargs = commands[0]
    assert command[:3] == [sys.executable, "--experiment-worker", "smoke"]
    assert "-u" not in command and "-m" not in command
    assert command[4] == str(tmp_path)
    assert kwargs["cwd"] == tmp_path
    assert manager.records[record["id"]]["status"] == "completed"
    assert manager.records[record["id"]]["history"][0]["validation"] == 0.002


def test_worker_rejects_unmanaged_paths_before_importing_or_training(tmp_path):
    paths = DesktopPaths(ROOT, tmp_path)
    with pytest.raises(ValueError, match="managed"):
        run_worker(paths, "smoke", ROOT)
    with pytest.raises(ValueError, match="preset"):
        run_worker(paths, "shell", tmp_path)
