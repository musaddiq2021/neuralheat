"""Verify source/asset correspondence to the already tested Windows installer.

Read-only by default. --record writes a small public provenance record only;
it never builds, trains, edits the application or changes a release binary.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

INSTALLER_SHA256 = "ecf3f57dcc2f8b50144c42e505559f71550d1f75466c3734aab16ec78d69171f"
CHECKPOINT_SHA256 = "d5e2d5a88c8666101279d696f04aa32c53159399938de126642e3e745c4429d2"
BASE_COMMIT = "00a1ba12496d4eb29c93ae638d9fce3502bcdb06"


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024**2), b""):
            result.update(block)
    return result.hexdigest()


def verify(root: Path) -> dict:
    """Fail on a changed application source, scientific asset or installer."""
    release = root / "dist/releases/v1.0.0-beta.1"
    candidate = json.loads((root / "reports/installer/20261027-093954-463/candidate.json")
                           .read_text(encoding="utf-8-sig"))
    bundle = Path(candidate["source_executable"]).parent
    if digest(release / "NeuralHeat-Studio-Setup.exe") != INSTALLER_SHA256:
        raise ValueError("Release installer does not match the approved SHA256")
    if digest(root / "models/best.pt") != CHECKPOINT_SHA256:
        raise ValueError("Reference checkpoint differs")
    installation = json.loads((Path(candidate["verified_report_directory"]) / "installer.json")
                              .read_text(encoding="utf-8-sig"))
    if installation["status"] != "verified" or not all(installation["checks"].values()):
        raise ValueError("Actual installation verification is incomplete")
    python_files = {}
    for source in sorted((root / "src/neuralheat").rglob("*.py")):
        target = bundle / "_internal/neuralheat" / source.relative_to(root / "src/neuralheat")
        if not target.is_file() or source.read_bytes() != target.read_bytes():
            raise ValueError(f"Python source differs from the frozen payload: {source}")
        python_files[source.relative_to(root).as_posix()] = digest(source)
    assets = bundle / "_internal/scientific_assets"
    manifest = json.loads((assets / "asset-manifest.json").read_text(encoding="utf-8"))
    matched = {}
    prefixes = ("frontend/dist/", "configs/", "data/", "models/", "reports/", "figures/")
    for name, expected in manifest["sha256"].items():
        if digest(assets / name) != expected:
            raise ValueError(f"Frozen asset changed: {name}")
        if name.startswith(prefixes):
            if not (root / name).is_file() or digest(root / name) != expected:
                raise ValueError(f"Release source/build asset differs: {name}")
            matched[name] = expected
    # Application sources were unchanged when the candidate was frozen; later
    # changes concern packaging, licences, tests and publication only.
    subprocess.run([
        "git", "diff", "--exit-code", BASE_COMMIT, "--", "src", "frontend/src",
        "frontend/vite.config.ts", "frontend/package.json", "package-lock.json",
        "scripts/desktop_entry.py",
    ], cwd=root, check=True, capture_output=True)
    return {
        "release": "v1.0.0-beta.1", "status": "verified_source_correspondence",
        "installer_sha256": INSTALLER_SHA256, "checkpoint_sha256": CHECKPOINT_SHA256,
        "application_base_commit": BASE_COMMIT,
        "python_source_comparison": "All collected Python source files are byte-identical.",
        "python_source_sha256": python_files,
        "compiled_ui_and_scientific_asset_sha256": matched,
        "frozen_assets_verified": len(manifest["sha256"]),
        "installed_payload_files_verified": installation["source_application_files"],
        "application_source_changes_since_base": False,
        "packaging_note": (
            "The installer uses the tested isolated Mg-free freeze. The production recipe "
            "subsequently adopted the equivalent guarded collection policy. Licence, "
            "packaging and publication documentation/scripts were finalised after freezing; "
            "the application, model and compiled UI were not rebuilt or changed."
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true")
    options = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    result = verify(project)
    if options.record:
        (project / "docs/verification/release-source.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "installer_sha256": INSTALLER_SHA256,
                      "python_source_files": len(result["python_source_sha256"]),
                      "matching_build_assets": len(result["compiled_ui_and_scientific_asset_sha256"]),
                      "frozen_assets_verified": result["frozen_assets_verified"]}, indent=2))
