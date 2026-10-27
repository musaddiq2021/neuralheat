"""Extract official runtime evidence without installing it or replacing any DLL.

The exact Microsoft installer is pinned to Microsoft's winget-pkgs manifest.
Windows expand.exe reads its embedded CAB containers; no runtime installer runs.
All extracted files stay in a fresh evidence directory outside application builds.
"""

import argparse
import hashlib
import json
import os
import struct
import subprocess
from pathlib import Path

INSTALLER_SHA256 = "3642e3f95d50cc193e4b5a0b0ffbf7fe2c08801517758b4c8aeb7105a091208a"
NUMPY_SHA256 = "a4c2229bdc2a2a630acdc095b4d86008e5c3e3bc7773174354f3da4f5beb9cde"
MANIFEST = (
    "https://github.com/microsoft/winget-pkgs/blob/master/manifests/m/Microsoft/"
    "VCRedist/2015%2B/x64/14.40.33810.0/Microsoft.VCRedist.2015%2B.x64.installer.yaml"
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cabinets(data: bytes):
    """Locate valid CAB headers, including Burn's attached containers."""
    offset = 0
    while (offset := data.find(b"MSCF", offset)) >= 0:
        if offset + 36 <= len(data):
            reserved, size = struct.unpack_from("<II", data, offset + 4)
            minor, major, folders, files = struct.unpack_from("<BBHH", data, offset + 24)
            if (reserved == 0 and 36 <= size <= len(data) - offset
                    and major == 1 and minor == 3 and folders and files):
                yield offset, data[offset:offset + size]
                offset += size
                continue
        offset += 4


def inspect(installer: Path, output: Path) -> dict:
    """Compare extracted signed-distribution bytes with NumPy's known DLL hash."""
    data = installer.read_bytes()
    if digest(data) != INSTALLER_SHA256:
        raise ValueError("Installer does not match Microsoft's pinned manifest; nothing extracted")
    if output.exists():
        raise FileExistsError("Use a fresh evidence output directory")
    output.mkdir(parents=True)
    expand = Path(os.environ["SystemRoot"]) / "System32/expand.exe"
    pending = [(str(installer), data)]
    seen, extracted, matches, licences = set(), [], [], []
    # The English runtime terms are in the bootstrapper CAB. Once those and
    # the exact DLL are found, other architecture/localization CABs add no evidence.
    while pending and not (matches and licences):
        source, payload = pending.pop(0)
        for offset, cabinet in cabinets(payload):
            cabinet_hash = digest(cabinet)
            if cabinet_hash in seen:
                continue
            seen.add(cabinet_hash)
            cabinet_path = output / f"container-{len(seen):02d}.cab"
            cabinet_path.write_bytes(cabinet)
            folder = output / f"container-{len(seen):02d}"
            folder.mkdir()
            result = subprocess.run(
                [str(expand), "-F:*", str(cabinet_path.resolve()), str(folder.resolve())],
                cwd=output, capture_output=True, timeout=90,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            (folder / "expand.log").write_bytes(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError(f"expand.exe failed for {cabinet_path}; inspect expand.log")
            extracted.append({"source": source, "offset": offset, "cab_sha256": cabinet_hash})
            for path in folder.rglob("*"):
                if not path.is_file() or path.name == "expand.log":
                    continue
                content = path.read_bytes()
                if digest(content) == NUMPY_SHA256:
                    matches.append({"path": str(path.resolve()), "bytes": len(content),
                                    "sha256": digest(content)})
                if content.lstrip().startswith(b"{\\rtf"):
                    licences.append({"path": str(path.resolve()), "sha256": digest(content)})
                if content.startswith(b"MSCF"):
                    pending.append((str(path.resolve()), content))
            if matches and licences:
                break
    evidence = {
        "installer": str(installer.resolve()), "installer_sha256": INSTALLER_SHA256,
        "official_manifest": MANIFEST, "cab_containers": extracted,
        "numpy_runtime_sha256": NUMPY_SHA256, "exact_matches": matches,
        "rtf_documents": licences, "runtime_installed": False,
        "application_modified": False,
        "status": "exact_runtime_match" if matches else "no_exact_match_found",
    }
    (output / "runtime-provenance.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = inspect(arguments.installer.resolve(), arguments.output.resolve())
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["exact_matches"] else 1)
