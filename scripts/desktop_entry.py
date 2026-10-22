"""PyInstaller boot script; frozen workers dispatch before creating any window."""

from neuralheat.desktop.main import main

if __name__ == "__main__":
    raise SystemExit(main())
