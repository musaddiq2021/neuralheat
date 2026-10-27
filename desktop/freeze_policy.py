"""Guarded collection policy proven by the isolated Windows Mg-free candidate.

This module only filters PyInstaller inputs. It never removes a DLL from an
existing application, changes PyTorch or alters scientific/model behaviour.
"""

from importlib.metadata import version
from pathlib import Path

TARGET = "cusolvermg64_11.dll"
VALIDATED_TORCH = "2.11.0+cu128"


def exclude_unused_cusolvermg(binary_rows: list, data_rows: list) -> list:
    """Omit only Mg and refuse unsafe imports or an unreviewed CUDA wheel."""
    if any(Path(row[0]).name.lower() == TARGET for row in data_rows):
        raise RuntimeError("cuSOLVERMg was unexpectedly collected as data")
    removed = [row for row in binary_rows if Path(row[0]).name.lower() == TARGET]
    if not removed:
        return list(binary_rows)  # CPU-only or already absent: no exclusion performed.
    if len(removed) != 1 or version("torch") != VALIDATED_TORCH:
        raise RuntimeError("Review a changed PyTorch wheel/collection before excluding cuSOLVERMg")

    import pefile

    kept = [row for row in binary_rows if Path(row[0]).name.lower() != TARGET]
    for destination, source, kind in kept:
        if kind not in {"BINARY", "EXTENSION"}:
            continue
        with pefile.PE(source, fast_load=True) as image:
            image.parse_data_directories(directories=[1, 13])
            imports = {
                entry.dll.decode("ascii").lower()
                for field in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT")
                for entry in getattr(image, field, [])
            }
            if TARGET in imports:
                raise RuntimeError(f"Refusing exclusion: {destination} imports cuSOLVERMg")
    return kept
