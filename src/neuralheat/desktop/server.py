"""Own one in-process ASGI backend on a reserved ephemeral loopback socket."""

import secrets
import socket
import threading
import time
from pathlib import Path


class DesktopServer:
    def __init__(self, assets: Path, user: Path, device: str = "auto"):
        self.assets, self.user, self.device = assets, user, device
        self.token = secrets.token_urlsafe(32)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        self.socket.bind(("127.0.0.1", 0))
        self.port = self.socket.getsockname()[1]
        self.origin = f"http://127.0.0.1:{self.port}"
        self.server = None
        self.app = None
        self.thread: threading.Thread | None = None
        self.error: BaseException | None = None
        self.stopping = threading.Event()

    @property
    def entry_url(self) -> str:
        return f"{self.origin}/desktop-session/{self.token}"

    def start(self, timeout: float = 120) -> None:
        if self.thread is not None:
            raise RuntimeError("Desktop backend already started")

        def run():
            try:
                import uvicorn

                from neuralheat.studio.app import create_app

                self.app = create_app(
                    self.assets,
                    self.device,
                    user_root=self.user,
                    desktop_origin=self.origin,
                    session_token=self.token,
                )
                self.server = uvicorn.Server(
                    uvicorn.Config(
                        self.app,
                        host="127.0.0.1",
                        port=self.port,
                        workers=1,
                        access_log=False,
                        log_config=None,
                        loop="asyncio",
                        http="h11",
                        ws="none",
                        lifespan="on",
                        timeout_graceful_shutdown=8,
                    )
                )
                if self.stopping.is_set():
                    return
                self.server.run(sockets=[self.socket])
            except BaseException as error:
                self.error = error

        self.thread = threading.Thread(target=run, name="neuralheat-backend", daemon=True)
        self.thread.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.stopping.is_set():
                raise RuntimeError("Application closed during backend startup")
            if self.error is not None:
                raise RuntimeError(f"Backend failed to start: {self.error}") from self.error
            if self.server and self.server.started:
                return
            if not self.thread.is_alive():
                raise RuntimeError("Backend stopped before becoming ready; inspect desktop.log")
            time.sleep(0.05)
        self.stop()
        raise TimeoutError("Scientific backend did not become ready within 120 seconds")

    def stop(self) -> None:
        self.stopping.set()
        # Stop experiment/SSE producers before waiting for ASGI connections.
        if self.app and hasattr(self.app.state, "experiments"):
            self.app.state.experiments.shutdown()
        if self.server:
            self.server.should_exit = True
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=15)
        self.socket.close()
