# -*- mode: python ; coding: utf-8 -*-
"""Windows x64 onedir release. Build only with scripts/build_desktop.ps1."""
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

root = Path(SPECPATH).parent
assets = Path(os.environ["NEURALHEAT_STAGED_ASSETS"])
if not (assets / "asset-manifest.json").is_file():
    raise RuntimeError("Stage and verify release assets before freezing")

datas = [(str(assets), "scientific_assets")]
datas += collect_data_files("webview")
datas += copy_metadata("pywebview") + copy_metadata("torch")
binaries = collect_dynamic_libs("torch") + collect_dynamic_libs("webview")

a = Analysis(
    [str(root / "scripts/desktop_entry.py")],
    pathex=[str(root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "neuralheat.dataset", "neuralheat.train", "neuralheat.evaluate", "neuralheat.benchmark",
        "neuralheat.desktop.worker", "neuralheat.desktop.verification",
        "webview.platforms.winforms", "webview.platforms.edgechromium",
        "uvicorn.logging", "uvicorn.loops.asyncio", "uvicorn.protocols.http.h11_impl",
        "uvicorn.lifespan.on", "pythonnet", "clr", "clr_loader",
    ],
    hookspath=[],
    hooksconfig={"matplotlib": {"backends": ["Agg"]}},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "cefpython3", "gtk", "gi", "tkinter", "IPython", "pytest"],
    # FX/inspect and scientific traceback tools can read the original sources.
    module_collection_mode={"neuralheat": "pyz+py"},
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="NeuralHeat Studio", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, disable_windowed_traceback=False,
    icon=str(root / "desktop/neuralheat.ico"),
    version=str(root / "desktop/version_info.txt"),
    contents_directory="_internal",
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="NeuralHeat Studio")
