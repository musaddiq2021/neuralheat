"""Installer verification must reject damaged payloads and incomplete runtime tests."""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from installer_release import report, runtime_checks, verify_installation, write_json


def make_manifest(source: Path) -> dict:
    paths = ("NeuralHeat Studio.exe", "_internal/scientific_assets/models/best.pt")
    for name in paths:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
    files = [
        {
            "path": name,
            "bytes": (source / name).stat().st_size,
            "sha256": hashlib.sha256((source / name).read_bytes()).hexdigest(),
        }
        for name in paths
    ]
    return {
        "bundle": str(source),
        "files": files,
        "uncompressed_bytes": sum(row["bytes"] for row in files),
    }


def test_installed_payload_allows_only_inno_uninstaller_extras(tmp_path):
    manifest = make_manifest(tmp_path)
    (tmp_path / "unins000.exe").write_bytes(b"uninstaller")
    (tmp_path / "unins000.dat").write_bytes(b"uninstall log")
    assert verify_installation(tmp_path, manifest)["status"] == "passed"
    (tmp_path / "unexpected.dll").write_bytes(b"unknown")
    result = verify_installation(tmp_path, manifest)
    assert result["status"] == "failed"
    assert result["unexpected"] == ["unexpected.dll"]


def test_installed_payload_detects_same_size_damage(tmp_path):
    manifest = make_manifest(tmp_path)
    exe = tmp_path / "NeuralHeat Studio.exe"
    exe.write_bytes(b"x" * exe.stat().st_size)
    result = verify_installation(tmp_path, manifest)
    assert result["status"] == "failed"
    assert result["changed"] == ["NeuralHeat Studio.exe"]


def test_frozen_ui_and_worker_evidence_are_required():
    common = {
        "status": "passed",
        "frozen": True,
        "backend_port_closed": True,
        "checkpoint_sha256": "checkpoint",
    }
    tests = {
        "installed-cpu": dict(common, device="cpu"),
        "installed-auto-worker": dict(
            common, device="cuda", worker={"smoke": "completed", "cancel": "passed"}
        ),
        "installed-webview": dict(
            common,
            webview2=dict.fromkeys(
                ("physics", "network", "training", "latency", "resize"), "passed"
            ),
        ),
    }
    assert all(runtime_checks(tests, "checkpoint").values())
    tests["installed-webview"]["frozen"] = False
    assert not all(runtime_checks(tests, "checkpoint").values())
    tests["installed-webview"]["frozen"] = True
    assert not all(runtime_checks(tests, "wrong-checkpoint").values())


def test_missing_install_evidence_cannot_produce_verified_report(tmp_path):
    source = tmp_path / "original"
    manifest = make_manifest(source)
    manifest_path = tmp_path / "manifest.json"
    write_json(manifest_path, manifest)
    installer = tmp_path / "NeuralHeat-Studio-Setup.exe"
    installer.write_bytes(b"installer fixture")
    result = report(
        {
            "source_manifest": str(manifest_path),
            "installer": str(installer),
            "source_cuda_verified": True,
        },
        {},
        tmp_path / "report",
    )
    assert result["status"] == "unverified"
    assert result["checks"]["source_unchanged"]
    assert not result["checks"]["installer_executed"]
    assert not result["checks"]["cuda_on_cuda_test_host"]
