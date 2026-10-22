"""FastAPI local workstation. Run one uvicorn worker to reuse one checkpoint."""

import asyncio
import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .experiments import ExperimentManager
from .schemas import ActivationRequest, ExperimentRequest, FieldRequest, SimulationRequest
from .service import StudioService

ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
}


def create_app(
    root: Path | None = None,
    device: str = "auto",
    *,
    user_root: Path | None = None,
    desktop_origin: str | None = None,
    session_token: str | None = None,
) -> FastAPI:
    project = (root or Path(__file__).resolve().parents[3]).resolve()
    origins = {desktop_origin} if desktop_origin else ORIGINS
    if desktop_origin and not session_token:
        raise ValueError("A desktop backend requires a session token")

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.service = await asyncio.to_thread(
            StudioService, project, device, user_root
        )
        application.state.experiments = ExperimentManager(project, work_root=user_root)
        yield
        await asyncio.to_thread(application.state.experiments.shutdown)

    application = FastAPI(title="NEURALHEAT Studio", version="1.0.0", lifespan=lifespan)
    application.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Last-Event-ID"],
    )

    @application.middleware("http")
    async def local_origin(request: Request, call_next):
        if request.headers.get("origin") and request.headers["origin"] not in origins:
            return JSONResponse(
                {"detail": "Only the local Studio origin is allowed"}, status_code=403
            )
        if session_token:
            if request.url.path == f"/desktop-session/{session_token}":
                response = RedirectResponse("/", status_code=303)
                response.set_cookie(
                    "neuralheat_session", session_token, httponly=True, samesite="strict"
                )
                response.headers["Referrer-Policy"] = "no-referrer"
                response.headers["Cache-Control"] = "no-store"
                return response
            if not hmac.compare_digest(
                request.cookies.get("neuralheat_session", ""), session_token
            ):
                return JSONResponse({"detail": "Desktop session required"}, status_code=401)
        return await call_next(request)

    @application.exception_handler(ValueError)
    async def invalid_request(_request: Request, error: ValueError):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @application.exception_handler(FileNotFoundError)
    async def missing_file(_request: Request, error: FileNotFoundError):
        return JSONResponse({"detail": str(error)}, status_code=404)

    @application.exception_handler(RuntimeError)
    async def unavailable(_request: Request, error: RuntimeError):
        return JSONResponse({"detail": str(error)}, status_code=503)

    @application.get("/api/health")
    def health(request: Request):
        service = request.app.state.service
        return {
            "status": "ready",
            "application": "NEURALHEAT Studio",
            "model_available": service.model is not None,
            "device": str(service.device),
            "active_experiment": request.app.state.experiments.active,
            "mode": "desktop" if desktop_origin else "development",
            "backend_address": desktop_origin or "http://127.0.0.1:8000",
        }

    @application.get("/api/model")
    def model(request: Request):
        return request.app.state.service.metadata()

    @application.get("/api/hardware")
    def hardware(request: Request):
        return request.app.state.service.gpu_status()

    @application.get("/api/runs")
    def runs(request: Request):
        return request.app.state.service.runs()

    @application.get("/api/runs/{identifier}")
    def run(identifier: str, request: Request):
        return request.app.state.service.run(identifier)

    @application.get("/api/training")
    def training(request: Request, run_id: str = "primary"):
        return {"run_id": run_id, "training": request.app.state.service.run(run_id)["training"]}

    @application.get("/api/runs/{identifier}/logs")
    def saved_logs(
        identifier: str,
        request: Request,
        kind: Literal["training", "benchmark", "data", "evaluation", "tests"] = "training",
    ):
        path = request.app.state.service.catalog().get(identifier)
        if path is None:
            raise FileNotFoundError("Saved run not found")
        log = path / "reports" / f"{kind}.log"
        text = log.read_text(encoding="utf-8", errors="replace")[-200000:] if log.exists() else ""
        return {"lines": text.splitlines(), "kind": kind, "run_id": identifier}

    @application.post("/api/simulate")
    def simulate(payload: SimulationRequest, request: Request):
        return request.app.state.service.simulate(payload)

    @application.post("/api/infer")
    def infer(payload: FieldRequest, request: Request):
        return request.app.state.service.infer(payload)

    @application.post("/api/activations")
    def activations(payload: ActivationRequest, request: Request):
        return request.app.state.service.activations(payload, payload.node_id)

    @application.get("/api/experiments")
    def experiments(request: Request):
        return request.app.state.experiments.history()

    @application.post("/api/experiments", status_code=201)
    def start_experiment(payload: ExperimentRequest, request: Request):
        try:
            return request.app.state.experiments.start(payload.preset)
        except OSError as error:
            raise RuntimeError(
                f"The operating system could not start the isolated experiment: {error}"
            ) from error

    @application.post("/api/experiments/{identifier}/cancel")
    def cancel_experiment(identifier: str, request: Request):
        return request.app.state.experiments.cancel(identifier)

    @application.get("/api/experiments/{identifier}/events")
    def stream_logs(
        identifier: str,
        request: Request,
        after: int = Query(0, ge=0),
        last_event_id: str | None = Header(default=None),
    ):
        manager = request.app.state.experiments
        manager.log_events(identifier, after)
        try:
            cursor = max(after, int(last_event_id or 0))
        except ValueError:
            cursor = after
        return StreamingResponse(
            manager.stream(identifier, cursor),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    distribution = project / "frontend/dist"
    if distribution.is_dir():
        application.mount("/", StaticFiles(directory=distribution, html=True), name="studio-ui")
    return application


app = create_app(device=os.environ.get("NEURALHEAT_DEVICE", "auto"))
