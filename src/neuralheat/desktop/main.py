"""Native desktop entry point; no Node.js, external browser, or Python CLI needed."""

import argparse
import ctypes
import html
import json
import logging
import logging.handlers
import multiprocessing
import os
import sys
import threading
import traceback
from pathlib import Path

from . import VERSION
from .paths import DesktopPaths, WorkspaceLock
from .server import DesktopServer

SPLASH = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{height:100%;margin:0;background:#111315;color:#edf0f2;font:15px 'Segoe UI',sans-serif}
body{display:grid;place-items:center;background-image:linear-gradient(#ffffff03 1px,transparent 1px),linear-gradient(90deg,#ffffff03 1px,transparent 1px);background-size:32px 32px}
main{width:480px;border-top:2px solid #a4b3bf;padding:30px 0}small{color:#99a4ad;letter-spacing:3px}h1{font-size:34px;font-weight:500;letter-spacing:-1px;margin:16px 0 8px}p{color:#9ca7af;line-height:1.7}code{font-size:12px;color:#7c8992}
.track{height:2px;background:#2c3338;margin:28px 0;overflow:hidden}.track:after{content:'';display:block;width:35%;height:100%;background:#a4b3bf;animation:load 1.8s ease-in-out infinite}
@keyframes load{from{transform:translateX(-110%)}to{transform:translateX(390%)}}@media(prefers-reduced-motion:reduce){.track:after{animation:none}}
</style></head><body><main><small>SCIENTIFIC COMPUTING WORKSTATION</small><h1>NEURALHEAT STUDIO</h1><p>Preparing the local physics engine and trained surrogate.</p><div class="track"></div><code>Offline workspace &nbsp; / &nbsp; float32 &nbsp; / &nbsp; CUDA with CPU fallback</code></main></body></html>"""


def configure_logging(paths: DesktopPaths) -> None:
    handler = logging.handlers.RotatingFileHandler(
        paths.user / "logs/desktop.log", maxBytes=4_000_000, backupCount=3, encoding="utf-8"
    )
    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler],
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
    # GUI-subsystem executables have no console streams. Keep libraries happy
    # and retain diagnostics without flashing a terminal window.
    if sys.stdout is None:
        sys.stdout = (paths.user / "logs/console.log").open("a", encoding="utf-8", buffering=1)
    if sys.stderr is None:
        sys.stderr = sys.stdout


def native_error(message: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, message, "NeuralHeat Studio", 0x10)
    else:
        print(message, file=sys.stderr)


def run_window(
    paths: DesktopPaths,
    server: DesktopServer,
    verification: dict | None = None,
    verify_worker: bool = False,
) -> None:
    import webview
    from webview.menu import Menu, MenuAction, MenuSeparator

    if os.name == "nt":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("NeuralHeat.Studio.1")
    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["ALLOW_FILE_URLS"] = False
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    icon = paths.assets / "desktop/neuralheat.ico"
    window = webview.create_window(
        "NeuralHeat Studio",
        html=SPLASH,
        background_color="#111315",
        min_size=(1000, 700),
        resizable=True,
        text_select=True,
        **paths.load_window(),
    )
    closed = threading.Event()
    window.events.closed += closed.set

    def style_native_frame():
        if os.name == "nt":
            try:
                from ctypes import wintypes

                dwm = ctypes.WinDLL("dwmapi")
                dwm.DwmSetWindowAttribute.argtypes = [
                    wintypes.HWND,
                    wintypes.DWORD,
                    ctypes.c_void_p,
                    wintypes.DWORD,
                ]
                dark = ctypes.c_int(1)
                handle = int(window.native.Handle.ToInt64())
                # Windows 10 before 20H1 used attribute 19 instead of 20.
                if dwm.DwmSetWindowAttribute(handle, 20, ctypes.byref(dark), 4) != 0:
                    dwm.DwmSetWindowAttribute(handle, 19, ctypes.byref(dark), 4)
            except Exception:
                logging.debug("System title-bar theme unavailable", exc_info=True)

    window.events.shown += style_native_frame

    def closing():
        if server.app and hasattr(server.app.state, "experiments"):
            if server.app.state.experiments.active and verification is None:
                if not window.create_confirmation_dialog(
                    "An experiment is running", "Close Studio and stop the active experiment?"
                ):
                    return False
        try:
            paths.save_window(window.width, window.height)
        except OSError:
            logging.exception("Could not save window size")
        return True

    window.events.closing += closing

    def navigate(page):
        if server.server and server.server.started:
            window.evaluate_js(f"location.hash = {json.dumps(page)}")

    menu = [
        Menu(
            "Workspace",
            [
                MenuAction(
                    "Open experiment folder", lambda: os.startfile(str(paths.user / "runs/studio"))
                ),
                MenuAction("Open application logs", lambda: os.startfile(str(paths.user / "logs"))),
                MenuSeparator(),
                MenuAction("Exit", window.destroy),
            ],
        ),
        Menu(
            "View",
            [
                MenuAction(title, lambda page=page: navigate(page))
                for page, title in [
                    ("overview", "Overview"),
                    ("physics", "Physics Lab"),
                    ("network", "Network Explorer"),
                    ("training", "Training Control Room"),
                    ("latency", "Latency Lab"),
                ]
            ],
        ),
    ]

    def bootstrap():
        try:
            paths.validate_assets()
            server.start()
            if closed.is_set():
                return
            window.load_url(server.entry_url)
            if verification is not None:
                from .verification import verify_backend, verify_ui

                verification.update(verify_backend(server, paths, verify_worker))
                verification["webview2"] = verify_ui(window)
                verification["status"] = "passed"
                window.destroy()
        except Exception as error:
            logging.exception("Desktop startup/verification failed")
            if verification is not None:
                verification.update(
                    status="failed", error=str(error), traceback=traceback.format_exc()
                )
                window.destroy()
            elif not closed.is_set():
                window.load_html(
                    "<body style='background:#111315;color:#e6ebee;font:16px Segoe UI;padding:64px'>"
                    "<h1>Studio could not start</h1><p>"
                    + html.escape(str(error))
                    + "</p><p>Logs: "
                    + html.escape(str(paths.user / "logs/desktop.log"))
                    + "</p></body>"
                )
        finally:
            if closed.is_set():
                server.stop()

    try:
        webview.start(
            bootstrap,
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(paths.user / "webview"),
            menu=menu,
            icon=str(icon) if icon.exists() else None,
        )
    finally:
        server.stop()


def main() -> int:
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-data-dir", type=Path)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--experiment-worker", choices=["smoke", "full"])
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--ui-test", action="store_true")
    parser.add_argument("--verify-worker", action="store_true")
    parser.add_argument("--test-report", type=Path)
    args = parser.parse_args()
    paths = DesktopPaths.discover(args.user_data_dir)
    result = {"version": VERSION, "status": "failed", "frozen": bool(getattr(sys, "frozen", False))}
    server = None
    workspace_lock = None
    try:
        paths.prepare()
        if args.experiment_worker:
            if not args.output_root:
                parser.error("Worker requires --output-root")
            from .worker import run_worker

            return run_worker(paths, args.experiment_worker, args.output_root)
        workspace_lock = WorkspaceLock(paths.user)
        configure_logging(paths)
        logging.info(
            "NeuralHeat Studio %s | assets=%s | user=%s", VERSION, paths.assets, paths.user
        )
        server = DesktopServer(paths.assets, paths.user, args.device)
        if args.self_test and not args.ui_test:
            from .verification import verify_backend

            paths.validate_assets()
            server.start()
            result.update(verify_backend(server, paths, args.verify_worker), status="passed")
        else:
            run_window(paths, server, result if args.self_test else None, args.verify_worker)
    except Exception as error:
        logging.exception("Application failed")
        result.update(status="failed", error=str(error), traceback=traceback.format_exc())
        if not args.self_test:
            native_error(
                f"NeuralHeat Studio could not start.\n\n{error}\n\n"
                f"Install the Microsoft Edge WebView2 Evergreen Runtime if missing.\n"
                f"Application logs: {paths.user / 'logs'}"
            )
    finally:
        if server:
            server.stop()
        if workspace_lock:
            workspace_lock.close()
        if args.self_test:
            from .verification import port_closed, save_result

            result["backend_port_closed"] = port_closed(server.port) if server else True
            if not result["backend_port_closed"]:
                result.update(status="failed", error="Internal backend port remained open")
            save_result(args.test_report or paths.user / "logs/self-test.json", result)
    return 0 if not args.self_test or result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
