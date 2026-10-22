"""Locate immutable bundle assets and per-user writable application state."""

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


class WorkspaceLock:
    """Prevent two desktop windows from managing the same experiment directory."""

    def __init__(self, user: Path):
        self.handle = None
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            key = hashlib.sha256(str(user).casefold().encode()).hexdigest()[:24]
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
            kernel.CreateMutexW.restype = ctypes.c_void_p
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            handle = kernel.CreateMutexW(None, False, "Local\\NeuralHeatStudio-" + key)
            error = ctypes.get_last_error()
            if not handle:
                raise ctypes.WinError(error)
            if error == 183:
                kernel.CloseHandle(handle)
                raise RuntimeError("NeuralHeat Studio is already running for this user workspace")
            self.handle, self.kernel = handle, kernel

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


@dataclass(frozen=True)
class DesktopPaths:
    assets: Path
    user: Path

    @classmethod
    def discover(cls, user_directory: Path | None = None) -> "DesktopPaths":
        if getattr(sys, "frozen", False):
            assets = Path(sys._MEIPASS) / "scientific_assets"
        else:
            assets = Path(__file__).resolve().parents[3]
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        return cls(assets.resolve(), (user_directory or local / "NeuralHeat Studio").resolve())

    def prepare(self) -> None:
        if self.user == self.assets or self.user.is_relative_to(self.assets):
            raise ValueError(
                "Desktop user data must be outside the read-only scientific asset tree"
            )
        for name in ("logs", "cache", "webview", "runs/studio", "settings"):
            (self.user / name).mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(self.user / "cache/matplotlib")
        os.environ["TORCH_HOME"] = str(self.user / "cache/torch")
        os.environ["XDG_CACHE_HOME"] = str(self.user / "cache")
        os.environ["MPLBACKEND"] = "Agg"

    def validate_assets(self) -> None:
        required = (
            "configs/full.json",
            "configs/smoke.json",
            "models/best.pt",
            "models/training.json",
            "reports/benchmark.json",
            "frontend/dist/index.html",
        )
        missing = [name for name in required if not (self.assets / name).is_file()]
        if missing:
            raise FileNotFoundError("Application assets are missing: " + ", ".join(missing))

    def load_window(self) -> dict:
        try:
            data = json.loads((self.user / "settings/window.json").read_text(encoding="utf-8"))
            return {
                "width": max(1000, min(3840, int(data["width"]))),
                "height": max(700, min(2160, int(data["height"]))),
            }
        except (OSError, ValueError, TypeError, KeyError):
            return {"width": 1480, "height": 980}

    def save_window(self, width: int, height: int) -> None:
        path = self.user / "settings/window.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"width": width, "height": height}), encoding="utf-8")
        temporary.replace(path)
