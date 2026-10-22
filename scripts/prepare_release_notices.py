"""Prepare additive public notices from local dependency evidence; never edit a build."""

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import shutil
import zipfile
from pathlib import Path

ROOTS = ("react", "react-dom", "@xyflow/react", "three", "tailwindcss")


def covered_source(root: Path, bundle: Path, destination: Path, output: Path) -> dict:
    """Supply certifi's matching editable source and full MPL, without changing it."""
    version = importlib.metadata.version("certifi")
    notices = (bundle / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
    if f"certifi {version}\n" not in notices:
        raise RuntimeError("Installed certifi version differs from the frozen build's record")
    spec = importlib.util.find_spec("certifi")
    if spec is None or spec.origin is None:
        raise RuntimeError("Cannot locate certifi source")
    source = Path(spec.origin).parent
    ca = bundle / "_internal/certifi/cacert.pem"
    if ca.read_bytes() != (source / "cacert.pem").read_bytes():
        raise RuntimeError("Local certifi CA source differs from the bundled certificate data")
    folder = destination / "covered-source" / f"certifi-{version}"
    folder.mkdir(parents=True, exist_ok=True)
    entries = {}
    for name in ("__init__.py", "__main__.py", "core.py", "py.typed", "cacert.pem"):
        data = (source / name).read_bytes()
        # .pem files are globally ignored for credential hygiene. This public CA
        # bundle is covered source; retain it as text and restore its name in ZIP.
        target = name + ".txt" if name == "cacert.pem" else name
        (folder / target).write_bytes(data)
        entries[f"certifi/{name}"] = data
    license_bytes = (destination / "python/certifi/00-LICENSE").read_bytes()
    (folder / "LICENSE").write_bytes(license_bytes)
    entries["LICENSE"] = license_bytes
    existing = (destination / "python/setuptools/23-NOTICE").read_text(encoding="utf-8")
    marker = "Mozilla Public License, version 2.0"
    mpl = marker + existing.split(marker, 1)[1]
    (destination / "vendor/Certifi-MPL-2.0.txt").write_text(mpl, encoding="utf-8")
    entries["MPL-2.0.txt"] = mpl.encode("utf-8")
    description = (
        f"certifi {version}: corresponding source for NeuralHeat Studio's frozen release.\n"
        "Unmodified editable Python modules and CA bundle from the matching build environment.\n"
        "The CA data was byte-compared against _internal/certifi/cacert.pem.\n"
        "No private keys: cacert.pem contains public certificate authority certificates.\n"
        "Under MPL-2.0; see LICENSE and MPL-2.0.txt.\n"
        f"Upstream: https://pypi.org/project/certifi/{version}/#files\n"
        "Source tree: docs/licenses/covered-source; rename cacert.pem.txt to cacert.pem.\n"
    )
    entries["SOURCE.txt"] = description.encode("utf-8")
    (folder / "SOURCE.txt").write_text(description, encoding="utf-8")
    archive = output / f"NeuralHeat-Studio-Certifi-{version}-Source.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
        for name, data in sorted(entries.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 10, 22, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            handle.writestr(entry, data)
    with zipfile.ZipFile(archive) as handle:
        if handle.testzip() or any(handle.read(name) != data for name, data in entries.items()):
            raise RuntimeError("Covered-source archive verification failed")
    return {
        "version": version,
        "bundled_ca_sha256": hashlib.sha256(ca.read_bytes()).hexdigest(),
        "source_files": {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()},
        "archive": archive.name,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "archive_verified": True,
    }


def prepare(root: Path, bundle: Path, output: Path) -> dict:
    destination = root / "docs/licenses"
    destination.mkdir(parents=True, exist_ok=True)
    python_source = bundle / "third-party-licenses"
    shutil.copytree(python_source, destination / "python", dirs_exist_ok=True)
    (destination / "python-environment-notices.txt").write_bytes(
        (bundle / "THIRD_PARTY_NOTICES.txt").read_bytes()
    )
    output.mkdir(parents=True, exist_ok=True)
    source_evidence = covered_source(root, bundle, destination, output)

    def resolve_package(name: str, context: Path) -> Path | None:
        for parent in (context, *context.parents):
            candidate = parent / "node_modules" / name
            if (candidate / "package.json").is_file():
                return candidate.resolve()
            if parent == root.parent:
                break
        return None

    pending = [(name, root / "frontend") for name in ROOTS] + [(name, root) for name in ROOTS]
    seen, packages, missing = set(), [], []
    while pending:
        name, context = pending.pop()
        package = resolve_package(name, context)
        if package is None:
            missing.append(name)
            continue
        if package in seen:
            continue
        seen.add(package)
        metadata = json.loads((package / "package.json").read_text(encoding="utf-8"))
        folder = (
            destination
            / "frontend"
            / (metadata["name"].replace("/", "_").replace("@", "") + "-" + metadata["version"])
        )
        folder.mkdir(parents=True, exist_ok=True)
        texts = []
        for source in sorted(package.iterdir()):
            if source.is_file() and source.name.lower().startswith(
                ("license", "licence", "copying", "notice")
            ):
                target = folder / source.name
                shutil.copy2(source, target)
                texts.append(target.relative_to(root).as_posix())
        if not texts:
            missing.append(f"license:{name}@{metadata['version']}")
        packages.append(
            {
                "name": metadata["name"],
                "version": metadata["version"],
                "declared_license": metadata.get("license", "not declared"),
                "license_files": texts,
            }
        )
        # Tailwind is included as build-tool evidence; its Node dependency tree
        # is not shipped in the generated CSS. Follow actual JS runtime deps.
        if name != "tailwindcss":
            pending.extend((child, package) for child in metadata.get("dependencies", {}))
            for peer in metadata.get("peerDependencies", {}):
                if resolve_package(peer, package) is not None:
                    pending.append((peer, package))
    result = {
        "scope": "Python license evidence from the existing frozen release; conservative installed frontend runtime dependency closure plus Tailwind's license. Not a claim that every listed package is bundled.",
        "frontend": sorted(packages, key=lambda row: (row["name"], row["version"])),
        "missing_frontend_evidence": sorted(set(missing)),
        "certifi_covered_source": source_evidence,
        "binary_release_review_required": json.loads(
            (destination / "redistribution-review.json").read_text(encoding="utf-8")
        )["outstanding"],
    }
    (destination / "inventory.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    output.mkdir(parents=True, exist_ok=True)
    combined = output / "NeuralHeat-Studio-Third-Party-Notices.txt"
    text = [
        "NEURALHEAT STUDIO - THIRD-PARTY NOTICES",
        "",
        "NeuralHeat's own code is MIT licensed. Dependencies retain their own licenses.",
        "Keep these notices and the accompanying covered-source ZIP with the installer.",
        "The publisher's MSVC entitlement remains pending; see the redistribution review below.",
        "",
        (root / "LICENSE").read_text(encoding="utf-8"),
        (root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"),
        (destination / "BINARY_DISTRIBUTION_TERMS.txt").read_text(encoding="utf-8"),
    ]
    for path in sorted(destination.rglob("*")):
        if path.is_file() and path.suffix != ".json" and "covered-source" not in path.parts:
            text.extend(
                [
                    "\n" + "=" * 72,
                    path.relative_to(root).as_posix(),
                    "=" * 72,
                    path.read_text(encoding="utf-8", errors="replace"),
                ]
            )
    combined.write_text("\n".join(text) + "\n", encoding="utf-8")
    sha = hashlib.sha256(combined.read_bytes()).hexdigest()
    combined.with_suffix(".txt.sha256").write_text(f"{sha}  {combined.name}\n", encoding="ascii")
    manifest_path = output / "release-assets.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {
            "published": False,
            "assets": [],
        }
    )
    additions = [combined, output / source_evidence["archive"]]
    for path in additions:
        record = {
            "file": path.name,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "local_path": str(path.relative_to(root)),
        }
        manifest["assets"] = [r for r in manifest["assets"] if r["file"] != path.name] + [record]
    manifest["binary_publication_ready"] = not result["binary_release_review_required"]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output / "SHA256SUMS.txt").write_text(
        "".join(f"{row['sha256']}  {row['file']}\n" for row in manifest["assets"]), encoding="ascii"
    )
    print(
        json.dumps(
            {
                "frontend_packages": len(packages),
                "missing_evidence": result["missing_frontend_evidence"],
                "sidecar": str(combined),
                "bytes": combined.stat().st_size,
            },
            indent=2,
        )
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.bundle is None:
        latest = json.loads((root / "dist/desktop/latest.json").read_text(encoding="utf-8-sig"))
        bundle = Path(latest["executable"]).parent
    else:
        bundle = args.bundle.resolve()
    result = prepare(root, bundle, args.output or root / "dist/release-support")
    raise SystemExit(1 if result["missing_frontend_evidence"] else 0)
