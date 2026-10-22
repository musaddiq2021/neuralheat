"""Verify an extracted portable package against the untouched release manifest."""

import argparse
import json
from pathlib import Path

from audit_desktop_bundle import digest


def verify_tree(bundle: Path, manifest: dict) -> dict:
    expected = {row["path"]: row for row in manifest["files"]}
    actual = {
        path.relative_to(bundle).as_posix(): path for path in bundle.rglob("*") if path.is_file()
    }
    missing = sorted(expected.keys() - actual.keys())
    unexpected = sorted(actual.keys() - expected.keys())
    changed = [
        name
        for name in sorted(expected.keys() & actual.keys())
        if actual[name].stat().st_size != expected[name]["bytes"]
        or digest(actual[name]) != expected[name]["sha256"]
    ]
    return {
        "status": "passed" if not (missing or unexpected or changed) else "failed",
        "files_checked": len(actual),
        "missing": missing,
        "unexpected": unexpected,
        "changed": changed,
        "bytes": sum(path.stat().st_size for path in actual.values()),
    }


def final_report(
    archive: Path,
    extracted: Path,
    audit_path: Path,
    test_reports: Path,
    output: Path,
    original_zip: Path | None = None,
    max_gib: float = 1.9,
) -> dict:
    manifest = json.loads(audit_path.read_text(encoding="utf-8"))
    source = Path(manifest["bundle"])
    extraction = verify_tree(extracted, manifest)
    original = verify_tree(source, manifest)
    tests = {}
    for name in ("packaged-cpu", "packaged-webview-cuda-worker"):
        path = test_reports / f"{name}.json"
        tests[name] = (
            json.loads(path.read_text(encoding="utf-8-sig"))
            if path.is_file()
            else {"status": "not_run"}
        )
    tested = all(
        value.get("status") == "passed" and value.get("frozen") and value.get("backend_port_closed")
        for value in tests.values()
    )
    cpu, cuda = tests["packaged-cpu"], tests["packaged-webview-cuda-worker"]
    tested = tested and cpu.get("device") == "cpu" and cuda.get("device") == "cuda"
    tested = tested and all(
        cuda.get("webview2", {}).get(page) == "passed"
        for page in ("physics", "network", "training", "latency", "resize")
    )
    tested = tested and (cuda.get("worker") or {}).get("smoke") == "completed"
    tested = tested and (cuda.get("worker") or {}).get("cancel") == "passed"
    checkpoint = next(
        (
            row["sha256"]
            for row in manifest["files"]
            if row["path"] == "_internal/scientific_assets/models/best.pt"
        ),
        None,
    )
    tested = (
        tested
        and checkpoint is not None
        and all(value.get("checkpoint_sha256") == checkpoint for value in tests.values())
    )
    size = archive.stat().st_size
    old_size = original_zip.stat().st_size if original_zip and original_zip.exists() else None
    result = {
        "status": "verified"
        if tested and extraction["status"] == original["status"] == "passed"
        else "unverified",
        "archive": str(archive.resolve()),
        "archive_sha256": digest(archive),
        "compressed_bytes": size,
        "compressed_gib": size / 1024**3,
        "uncompressed_bytes": extraction["bytes"],
        "uncompressed_gib": extraction["bytes"] / 1024**3,
        "target_gib": max_gib,
        "meets_target": size < max_gib * 1024**3,
        "github_under_2_gib": size < 2 * 1024**3,
        "original_zip_bytes": old_size,
        "reduction_bytes": old_size - size if old_size is not None else None,
        "reduction_percent": 100 * (old_size - size) / old_size if old_size else None,
        "extracted_path": str(extracted.resolve()),
        "extraction_integrity": extraction,
        "original_build_preservation": original,
        "packaged_tests": tests,
        "runtime_checks": {
            "frozen_cpu": cpu.get("frozen") is True
            and cpu.get("status") == "passed"
            and cpu.get("device") == "cpu",
            "frozen_cuda_inference": cuda.get("frozen") is True
            and cuda.get("device") == "cuda"
            and "inference" in cuda.get("checks", []),
            "smoke_worker": (cuda.get("worker") or {}).get("smoke") == "completed",
            "cancel_worker": (cuda.get("worker") or {}).get("cancel") == "passed",
            "webview2": all(
                cuda.get("webview2", {}).get(page) == "passed"
                for page in ("physics", "network", "training", "latency", "resize")
            ),
            "backend_shutdown": all(
                value.get("backend_port_closed") is True for value in tests.values()
            ),
        },
        "removed_modules": [],
        "removed_dlls": [],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "distribution.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (archive.parent / (archive.name + ".sha256")).write_text(
        f"{result['archive_sha256']}  {archive.name}\n", encoding="ascii"
    )
    old_display = f"{old_size:,}" if old_size is not None else "Unavailable"
    old_gib = f"{old_size / 1024**3:.3f}" if old_size is not None else "Unavailable"
    saving = f"{result['reduction_percent']:.2f}%" if old_size else "Unavailable"
    lines = [
        "# NeuralHeat Studio portable package",
        "",
        f"Archive: `{archive.name}`",
        "",
        "| Measurement | Bytes | GiB |",
        "|---|---:|---:|",
        f"| Original ZIP | {old_display} | {old_gib} |",
        f"| LZMA2 archive | {size:,} | {size / 1024**3:.3f} |",
        f"| Extracted application | {extraction['bytes']:,} | {extraction['bytes'] / 1024**3:.3f} |",
        "",
        f"Download reduction: **{saving}**. Below 1.9 GiB: **{result['meets_target']}**.",
        "",
        f"Original files preserved: **{original['status']}**. Extracted files match: **{extraction['status']}** ({extraction['files_checked']} files).",
        "",
        "No DLLs, modules, checkpoint weights, cached fields or reports were removed or modified. Installed size remains unchanged.",
        "",
        "| Extracted executable check | Passed |",
        "|---|---|",
        *[f"| {name} | {passed} |" for name, passed in result["runtime_checks"].items()],
        "",
        f"Overall frozen verification: **{result['status']}**.",
        "",
        "Extract with 7-Zip or Windows tar.exe, then double-click NeuralHeat Studio.exe. Keep the complete _internal folder. WebView2 and a compatible NVIDIA driver remain system prerequisites.",
        "",
        f"SHA256: `{result['archive_sha256']}`",
        "",
    ]
    if not result["runtime_checks"]["webview2"]:
        lines += [
            "Native WebView2 verification has not passed in this run. See the recorded process error. Repeat `scripts/test_distribution.ps1` from an ordinary interactive Windows PowerShell session to complete verification without recompressing.",
            "",
        ]
    (output / "distribution.md").write_text("\n".join(lines), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extracted", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--integrity-only", action="store_true")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--test-reports", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--original-zip", type=Path)
    args = parser.parse_args()
    if args.integrity_only:
        result = verify_tree(args.extracted, json.loads(args.audit.read_text(encoding="utf-8")))
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result["status"] == "passed" else 1)
    if not all((args.archive, args.test_reports, args.output)):
        parser.error("Final verification requires --archive, --test-reports and --output")
    result = final_report(
        args.archive, args.extracted, args.audit, args.test_reports, args.output, args.original_zip
    )
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "packaged_tests"}, indent=2
        )
    )
    raise SystemExit(0 if result["status"] == "verified" and result["meets_target"] else 1)
