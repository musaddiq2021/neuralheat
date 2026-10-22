"""Capture the existing production interface with real API data; never build or train."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from neuralheat.desktop.paths import DesktopPaths
from neuralheat.desktop.server import DesktopServer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", choices=("chrome", "msedge"), default="chrome")
    parser.add_argument("--output", type=Path, default=Path("docs/screenshots"))
    parser.add_argument("--assets", type=Path, help="Existing packaged scientific_assets directory")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    assets = args.assets
    if assets is None:
        release = json.loads((root / "dist/desktop/latest.json").read_text(encoding="utf-8-sig"))
        assets = Path(release["executable"]).parent / "_internal/scientific_assets"
    if not (assets / "frontend/dist/index.html").is_file():
        raise FileNotFoundError(
            "An existing production asset snapshot is required; this command never builds it"
        )
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required on the developer capture machine")
    paths = DesktopPaths(assets.resolve(), root / ".cache/publication-screenshots/user")
    paths.prepare()
    paths.validate_assets()
    server = DesktopServer(paths.assets, paths.user)
    try:
        server.start()
        env = dict(os.environ)
        env["NEURALHEAT_CAPTURE_ENTRY"] = server.entry_url
        env["NEURALHEAT_CAPTURE_BROWSER"] = args.browser
        env["NEURALHEAT_CAPTURE_OUTPUT"] = str(args.output.resolve())
        subprocess.run(
            [node, str(root / "frontend/scripts/capture-release.mjs")],
            cwd=root,
            env=env,
            check=True,
        )
    finally:
        server.stop()
    print(
        json.dumps(
            {"output": str(args.output), "training_started": False, "frontend_rebuilt": False}
        )
    )


if __name__ == "__main__":
    main()
