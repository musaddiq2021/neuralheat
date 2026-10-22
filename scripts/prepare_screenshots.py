"""Losslessly compress the maintainer's actual captures; preserve all originals."""

import hashlib
import io
import json
from pathlib import Path

from PIL import Image

CAPTURES = {
    "loading": ("Screenshot 2026-10-22 120044.png", "Native desktop loading screen"),
    "overview": ("Screenshot 2026-10-22 120110.png", "System Overview with saved results"),
    "physics": ("Screenshot 2026-10-22 120124.png", "Physics Lab at numerical step 120"),
    "network": ("Screenshot 2026-10-22 120144.png", "Network Explorer with Encoder 01 selected"),
}


def prepare(folder: Path) -> dict:
    """Keep dimensions and every decoded RGBA pixel unchanged, with no retouching."""
    records = []
    for name, (filename, description) in CAPTURES.items():
        source = folder / filename
        original = source.read_bytes()
        with Image.open(source) as capture:
            buffer = io.BytesIO()
            capture.save(buffer, format="PNG", optimize=True, compress_level=9)
            encoded = buffer.getvalue()
            # Do not increase the file size when the supplied PNG is smaller.
            prepared = encoded if len(encoded) < len(original) else original
            with Image.open(io.BytesIO(prepared)) as check:
                identical = (
                    capture.size == check.size
                    and capture.convert("RGBA").tobytes() == check.convert("RGBA").tobytes()
                )
            if not identical:
                raise RuntimeError(f"Pixel verification failed: {filename}")
            (folder / f"{name}.png").write_bytes(prepared)
            records.append(
                {
                    "image": f"{name}.png",
                    "description": description,
                    "source": filename,
                    "width": capture.width,
                    "height": capture.height,
                    "source_bytes": len(original),
                    "bytes": len(prepared),
                    "source_sha256": hashlib.sha256(original).hexdigest(),
                    "sha256": hashlib.sha256(prepared).hexdigest(),
                    "rgba_sha256": hashlib.sha256(capture.convert("RGBA").tobytes()).hexdigest(),
                    "pixels_identical": identical,
                }
            )
    result = {
        "method": "manual Windows captures supplied by the maintainer",
        "reviewed": "2026-10-22",
        "processing": "Lossless PNG compression only; no crop, resizing or generated content",
        "scope": "Visual provenance only, not an automated checkpoint or API verification record",
        "gallery_scope": "Maintainer approved using the available captures; no training/latency captures supplied",
        "images": records,
    }
    (folder / "provenance.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(prepare(root / "docs/screenshots"), indent=2))
