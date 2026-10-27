"""Prepare local GitHub prerelease assets; never tag, push or publish.

An old retained-Mg installer cannot become an upload-ready release by copying it.
The existing licence review and real installer verification must pass first.
"""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

TAG = "v1.0.0-beta.1"
CHECKPOINT = "d5e2d5a88c8666101279d696f04aa32c53159399938de126642e3e745c4429d2"


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024**2), b""):
            result.update(block)
    return result.hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def prepare(root: Path, candidate_file: Path, destination: Path) -> dict:
    """Stage only a genuinely verified installer, or write an explicit draft."""
    destination.mkdir(parents=True, exist_ok=True)
    review = read(root / "docs/licenses/redistribution-review.json")
    candidate = read(candidate_file)
    bundle = Path(candidate["source_executable"]).parent
    installer = Path(candidate["installer"])
    reasons = list(review["outstanding"])
    if not review["binary_publication_ready"] and not reasons:
        reasons.append("Redistribution review has not been completed.")
    if (bundle / "_internal/torch/lib/cusolverMg64_11.dll").exists():
        reasons.append("This installer source retains cuSOLVERMg; it is not the exclusion release.")
    verification_path = installer.parent / "installer.json"
    verification = read(verification_path) if verification_path.is_file() else {}
    if verification.get("status") != "verified":
        reasons.append("The final installer has no completed installation verification.")
    if not installer.is_file():
        reasons.append("The final installer has not been built.")
    elif installer.stat().st_size >= 2 * 1024**3:
        reasons.append("Installer exceeds GitHub's per-asset size limit.")
    if digest(root / "models/best.pt") != CHECKPOINT:
        raise RuntimeError("Reference checkpoint has changed; no release prepared")
    files = []
    if not reasons:
        if digest(installer) != candidate["installer_sha256"]:
            raise RuntimeError("Installer differs from its verified candidate record")
        if verification.get("installer_sha256") != candidate["installer_sha256"]:
            raise RuntimeError("Installation verification belongs to a different installer")
        support = root / "dist/release-support"
        sources = [installer, root / "models/best.pt",
                   support / "NeuralHeat-Studio-Third-Party-Notices.txt",
                   support / "NeuralHeat-Studio-Certifi-2026.4.22-Source.zip"]
        for source in sources:
            target = destination / source.name
            if target.exists() and digest(target) != digest(source):
                raise FileExistsError(f"Existing release asset differs; preserve it: {target}")
            if not target.exists():
                shutil.copyfile(source, target)
            files.append({"name": target.name, "bytes": target.stat().st_size,
                          "sha256": digest(target)})
        (destination / "SHA256SUMS.txt").write_text(
            "".join(f"{f['sha256']}  {f['name']}\n" for f in files), encoding="ascii")
    report = {
        "tag_name": TAG, "name": "NeuralHeat Studio v1.0.0-beta.1", "prerelease": True,
        "published": False, "remote_draft_created": False,
        "status": "ready_for_upload" if not reasons else "draft_awaiting_evidence",
        "remaining": reasons, "assets": files,
        "candidate_installer": str(installer),
        "upload_ready_installer": str(destination / installer.name) if not reasons else None,
        "source_candidate_file": str(candidate_file),
        "checkpoint_sha256": CHECKPOINT,
    }
    (destination / "release-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    notes = (root / "docs/RELEASE_NOTES.md").read_text(encoding="utf-8")
    if reasons:
        notes = "**Draft: not ready for upload. See release-manifest.json for pending evidence.**\n\n" + notes
    else:
        notes = "\n".join(line for line in notes.splitlines()
                          if not line.startswith("**Maintainer publication gate:**")) + "\n"
        notes = notes.replace("— prerelease draft", "— Windows prerelease")
        notes = notes.replace(
            "Final size and SHA256 will be generated from the verified Mg-free installer; "
            "the older installer's size is not a measurement of this candidate.",
            "The verified Mg-free installer's measured size and SHA256 are listed below.",
        )
        measured = next(asset for asset in files if asset["name"] == installer.name)
        notes += (f"\nVerified installer: {measured['bytes']:,} bytes "
                  f"({measured['bytes'] / 1e9:.6f} GB / {measured['bytes'] / 1024**3:.6f} GiB).\n\n"
                  f"SHA256: `{measured['sha256']}`\n")
    (destination / "release-notes.md").write_text(notes, encoding="utf-8")
    if not reasons:
        # Deliberately documentation, never automatically executed.
        command = (
            "# Run only after committing/reviewing the release source and creating its tag.\n"
            "# This creates a draft prerelease, not a public release.\n"
            "$ErrorActionPreference = 'Stop'\n"
            "$release = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'release-manifest.json') -Raw | ConvertFrom-Json\n"
            "if ($release.status -ne 'ready_for_upload') { throw 'Release verification is incomplete.' }\n"
            "foreach ($asset in $release.assets) {\n"
            "  $actual = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $asset.name) -Algorithm SHA256).Hash.ToLowerInvariant()\n"
            "  if ($actual -ne $asset.sha256) { throw ('Release asset changed: ' + $asset.name) }\n"
            "}\n"
            "Push-Location -LiteralPath $PSScriptRoot\ntry {\n"
            "gh release create v1.0.0-beta.1 --repo musaddiq2021/neuralheat --verify-tag "
            "--draft --prerelease --title 'NeuralHeat Studio v1.0.0-beta.1' "
            "--notes-file release-notes.md NeuralHeat-Studio-Setup.exe best.pt "
            "NeuralHeat-Studio-Third-Party-Notices.txt "
            "NeuralHeat-Studio-Certifi-2026.4.22-Source.zip SHA256SUMS.txt\n"
            "if ($LASTEXITCODE -ne 0) { throw 'GitHub draft creation failed.' }\n"
            "} finally { Pop-Location }\n"
        )
        (destination / "CREATE_GITHUB_DRAFT.ps1").write_text(command, encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path("reports/installer/candidate.json"))
    parser.add_argument("--output", type=Path, default=Path("dist/releases") / TAG)
    arguments = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    result = prepare(project, arguments.candidate.resolve(), arguments.output.resolve())
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "ready_for_upload" else 2)
