"""Release checks executed by the frozen application, using its own assets."""

import hashlib
import http.cookiejar
import json
import socket
import sys
import time
import urllib.request
from pathlib import Path

from .paths import DesktopPaths
from .server import DesktopServer


def verify_backend(server: DesktopServer, paths: DesktopPaths, verify_worker: bool = False) -> dict:
    import numpy as np

    from neuralheat.solver import solve

    jar = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar)
    )
    client.open(server.entry_url, timeout=30).read()

    def get(path: str, payload: dict | None = None):
        request = urllib.request.Request(
            server.origin + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Content-Type": "application/json", "Origin": server.origin},
        )
        with client.open(request, timeout=60) as response:
            return json.load(response)

    health = get("/api/health")
    if health["active_experiment"] is not None:
        raise AssertionError("Opening the application started an experiment")
    if not health["model_available"]:
        raise AssertionError("Bundled checkpoint failed to load")
    model = get("/api/model")
    saved = get("/api/runs/primary")
    original = json.loads((paths.assets / "reports/benchmark.json").read_text(encoding="utf-8"))
    assert saved["benchmark"] == original
    simulation = get("/api/simulate", {"sample_index": 0, "frame_stride": 40})
    service = server.app.state.service
    reference = solve(np.array(simulation["initial"], dtype=np.float32), service.physics)
    np.testing.assert_array_equal(simulation["frames"][-1]["field"], reference)
    inference = get("/api/infer", {"sample_index": 0})
    np.testing.assert_allclose(inference["prediction"], simulation["prediction"], rtol=0, atol=0)
    for node in ("initial", "encoder1", "bottleneck", "output"):
        activation = get("/api/activations", {"node_id": node, "sample_index": 0})
        assert np.isfinite(np.asarray(activation["channels"])).all()
    assert get("/api/runs/primary/logs?kind=training")["lines"]
    manifest = paths.assets / "asset-manifest.json"
    checked = 0
    if manifest.exists():
        for name, expected in json.loads(manifest.read_text(encoding="utf-8"))["sha256"].items():
            path = paths.assets / name
            if not path.resolve().is_relative_to(paths.assets):
                raise ValueError("Invalid bundled asset manifest path")
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
            checked += 1
    worker = None
    if verify_worker:
        record = get("/api/experiments", {"preset": "smoke"})
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            record = next(item for item in get("/api/experiments") if item["id"] == record["id"])
            if record["status"] in {"completed", "cancelled", "failed"}:
                break
            time.sleep(0.3)
        else:
            get(f"/api/experiments/{record['id']}/cancel", {})
            raise TimeoutError("Frozen smoke worker exceeded five minutes")
        assert record["status"] == "completed", record
        report = paths.user / record["relative_path"] / "reports/benchmark.json"
        assert json.loads(report.read_text(encoding="utf-8"))["status"] == "completed"
        cancelled = get("/api/experiments", {"preset": "smoke"})
        get(f"/api/experiments/{cancelled['id']}/cancel", {})
        deadline = time.monotonic() + 15
        while get("/api/health")["active_experiment"] and time.monotonic() < deadline:
            time.sleep(0.1)
        assert get("/api/health")["active_experiment"] is None
        worker = {"smoke": "completed", "cancel": "passed", "run": record["relative_path"]}
    return {
        "frozen": bool(getattr(sys, "frozen", False)),
        "device": health["device"],
        "backend_origin": server.origin,
        "model_parameters": model["parameters"],
        "checkpoint_sha256": model["checkpoint_sha256"],
        "asset_hashes_verified": checked,
        "graph_nodes": len(model["graph"]["nodes"]),
        "graph_edges": len(model["graph"]["edges"]),
        "checks": [
            "offline static UI",
            "session cookie",
            "saved report unchanged",
            "solver agreement",
            "inference",
            "real activations",
            "saved logs",
            "idle on launch",
        ],
        "worker": worker,
    }


def verify_ui(window) -> dict:
    """Check real WebView2 DOM and activations, including lazy-loaded graph code."""
    pages = {
        "physics": "Physics Lab",
        "network": "Neural Network Explorer",
        "training": "Training Control Room",
        "latency": "Latency Lab",
    }
    checks = {}
    window.evaluate_js(
        "window.__neuralheatErrors = [];"
        "window.addEventListener('error', e => window.__neuralheatErrors.push(e.message));"
        "window.addEventListener('unhandledrejection', e => window.__neuralheatErrors.push(String(e.reason)));"
    )
    for page, title in pages.items():
        window.evaluate_js(f"location.hash = {json.dumps(page)}")
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            ready = window.evaluate_js(
                f"Array.from(document.querySelectorAll('h1')).some(h => h.textContent === {json.dumps(title)})"
            )
            if page == "network":
                ready = ready and window.evaluate_js(
                    "document.querySelectorAll('.react-flow__node').length === 17 && !!document.querySelector('.activation-panel canvas')"
                )
            if page == "physics":
                ready = ready and window.evaluate_js(
                    "document.querySelectorAll('.heat-panel canvas').length === 4"
                )
            if ready:
                break
            time.sleep(0.1)
        else:
            raise AssertionError(f"WebView2 page did not become ready: {page}")
        checks[page] = "passed"
    window.resize(1100, 780)
    time.sleep(0.2)
    assert window.evaluate_js("document.documentElement.scrollWidth <= innerWidth + 1")
    assert not window.evaluate_js("window.__neuralheatErrors"), (
        "WebView2 reported JavaScript errors"
    )
    checks["resize"] = "passed"
    return checks


def port_closed(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(1)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def save_result(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
