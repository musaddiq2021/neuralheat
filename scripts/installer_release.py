"""Inventory installer inputs and verify installed files and real runtime evidence."""

import argparse
import json
import re
from pathlib import Path

from audit_desktop_bundle import audit, digest
from verify_distribution import verify_tree

APP_ID = "{6E55B462-28F0-4C8A-98C5-E896B4D52631}"
REQUIRED = (
    "NeuralHeat Studio.exe",
    "LICENSE.txt",
    "_internal/scientific_assets/asset-manifest.json",
    "_internal/scientific_assets/models/best.pt",
    "_internal/scientific_assets/models/training.json",
    "_internal/scientific_assets/reports/benchmark.json",
    "_internal/scientific_assets/frontend/dist/index.html",
    "_internal/scientific_assets/configs/full.json",
    "_internal/scientific_assets/configs/smoke.json",
    "_internal/scientific_assets/desktop/neuralheat.ico",
    "_internal/torch/lib/torch_cpu.dll",
    "_internal/torch/lib/torch_cuda.dll",
    "_internal/torch/lib/cublasLt64_12.dll",
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def prepare(source: Path, output: Path) -> dict:
    """Reject incomplete sources and retain every source file's SHA256."""
    missing = [name for name in REQUIRED if not (source / name).is_file()]
    if missing:
        raise FileNotFoundError("Incomplete desktop release: " + ", ".join(missing))
    assets = source / "_internal/scientific_assets"
    scientific = read_json(assets / "asset-manifest.json")
    for name, expected in scientific["sha256"].items():
        path = (assets / name).resolve()
        if not path.is_relative_to(assets.resolve()) or digest(path) != expected:
            raise ValueError(f"Bundled scientific asset failed integrity verification: {name}")
    return audit(source, output)


def verify_installation(installed: Path, manifest: dict) -> dict:
    """Only Inno Setup's exact uninstaller filenames may augment the source tree."""
    result = verify_tree(installed, manifest)
    extras = result["unexpected"]
    result["installer_files"] = [
        name for name in extras if re.fullmatch(r"unins\d{3}\.(exe|dat|msg)", name)
    ]
    result["unexpected"] = [name for name in extras if name not in result["installer_files"]]
    result["status"] = (
        "passed"
        if not (result["missing"] or result["unexpected"] or result["changed"])
        else "failed"
    )
    result["application_files_checked"] = len(manifest["files"]) - len(result["missing"])
    return result


def runtime_checks(tests: dict, checkpoint: str) -> dict:
    """Never accept a passing development run or stale/mismatched checkpoint."""
    checks = {}
    for name in ("installed-cpu", "installed-auto-worker", "installed-webview"):
        row = tests.get(name, {})
        checks[name] = bool(
            row.get("status") == "passed"
            and row.get("frozen") is True
            and row.get("backend_port_closed") is True
            and row.get("checkpoint_sha256") == checkpoint
        )
    checks["cpu_fallback"] = tests.get("installed-cpu", {}).get("device") == "cpu"
    auto = tests.get("installed-auto-worker", {})
    checks["automatic_device"] = auto.get("device") in {"cpu", "cuda"}
    # CUDA is required on a host where the exact source release verified it.
    worker = auto.get("worker") or {}
    checks["training_and_cancel"] = (
        worker.get("smoke") == "completed" and worker.get("cancel") == "passed"
    )
    pages = tests.get("installed-webview", {}).get("webview2", {})
    checks["all_ui_pages_and_resize"] = all(
        pages.get(name) == "passed"
        for name in ("physics", "network", "training", "latency", "resize")
    )
    return checks


def report(candidate: dict, evidence: dict, output: Path) -> dict:
    manifest = read_json(Path(candidate["source_manifest"]))
    archive = Path(candidate["installer"])
    preservation = verify_tree(Path(manifest["bundle"]), manifest)
    checkpoint = next(
        row["sha256"]
        for row in manifest["files"]
        if row["path"] == "_internal/scientific_assets/models/best.pt"
    )
    tests = {}
    for name in ("installed-cpu", "installed-auto-worker", "installed-webview"):
        path = output / f"{name}.json"
        tests[name] = read_json(path) if path.exists() else {"status": "not_run"}
    checks = runtime_checks(tests, checkpoint)
    auto = tests["installed-auto-worker"]
    checks["cuda_on_cuda_test_host"] = (
        auto.get("device") == "cuda" if candidate.get("source_cuda_verified") else True
    )
    checks["installer_executed"] = evidence.get("install_exit_code") == 0
    checks["uninstall_registration"] = evidence.get("registration", {}).get("status") == "passed"
    checks["shortcuts"] = evidence.get("shortcuts", {}).get("status") == "passed"
    checks["installed_integrity"] = evidence.get("integrity_after", {}).get("status") == "passed"
    checks["default_appdata_location"] = evidence.get("appdata_verified") is True
    checks["source_unchanged"] = preservation["status"] == "passed"
    if evidence.get("uninstall_requested"):
        checks["uninstall_preserves_personal_data"] = (
            evidence.get("uninstall", {}).get("status") == "passed"
        )
    result = {
        "status": "verified" if all(checks.values()) else "unverified",
        "installer": str(archive.resolve()),
        "installer_bytes": archive.stat().st_size,
        "installer_gb": archive.stat().st_size / 1e9,
        "installer_gib": archive.stat().st_size / 1024**3,
        "installer_sha256": digest(archive),
        "source_application_bytes": manifest["uncompressed_bytes"],
        "source_application_files": len(manifest["files"]),
        "source_executable": str(Path(manifest["bundle"]) / "NeuralHeat Studio.exe"),
        "source_preservation": preservation,
        "offline_application_payload": True,
        "webview2_offline_installer_bundled": bool(candidate.get("webview2_installer")),
        "webview2_required_preinstalled": not bool(candidate.get("webview2_installer")),
        "signing": "unsigned",
        "checks": checks,
        "installation": evidence,
        "runtime_tests": tests,
    }
    write_json(output / "installer.json", result)
    summary = (
        "# NeuralHeat Studio Windows installer\n\n"
        f"Status: **{result['status']}**\n\n"
        f"Installer: `{archive}`\n\n"
        f"Compressed: {result['installer_gb']:.6f} GB / {result['installer_gib']:.6f} GiB "
        f"({result['installer_bytes']:,} bytes).\n\n"
        f"Complete application: {len(manifest['files']):,} files, "
        f"{manifest['uncompressed_bytes']:,} bytes.\n\n"
        "The installer contains all application dependencies and makes no downloads. "
        + (
            "The offline WebView2 installer is included.\n\n"
            if candidate.get("webview2_installer")
            else "Microsoft WebView2 Runtime must already be installed.\n\n"
        )
        + "A compatible NVIDIA driver is required for CUDA; CPU fallback is included. "
        "The release is unsigned. Windows SmartScreen may require confirmation.\n\n"
        "| Verification | Result |\n|---|---|\n"
        + "".join(
            f"| {name} | {'passed' if passed else 'not verified'} |\n"
            for name, passed in checks.items()
        )
        + "\nSee installer.json and install.log for actual installation and runtime evidence.\n"
    )
    (output / "installer.md").write_text(summary, encoding="utf-8")
    (archive.parent / (archive.name + ".sha256")).write_text(
        result["installer_sha256"] + "  " + archive.name + "\n", encoding="ascii"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_command = commands.add_parser("prepare")
    prepare_command.add_argument("--source", type=Path, required=True)
    prepare_command.add_argument("--output", type=Path, required=True)
    verify_command = commands.add_parser("verify")
    verify_command.add_argument("--installed", type=Path, required=True)
    verify_command.add_argument("--manifest", type=Path, required=True)
    verify_command.add_argument("--output", type=Path, required=True)
    report_command = commands.add_parser("report")
    report_command.add_argument("--candidate", type=Path, required=True)
    report_command.add_argument("--evidence", type=Path, required=True)
    report_command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.source, args.output)
    elif args.command == "verify":
        result = verify_installation(args.installed, read_json(args.manifest))
        write_json(args.output, result)
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result["status"] == "passed" else 1)
    else:
        result = report(read_json(args.candidate), read_json(args.evidence), args.output)
        print(
            json.dumps(
                {key: result[key] for key in ("status", "installer", "installer_bytes", "checks")},
                indent=2,
            )
        )
        raise SystemExit(0 if result["status"] == "verified" else 1)
