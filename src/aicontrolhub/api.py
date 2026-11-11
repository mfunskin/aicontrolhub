"""Local-only API for AI governance recording and deterministic release gates."""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from aicontrolhub.models import (
    ApproveRelease,
    ControlEvidence,
    CreateRelease,
    CreateRisk,
    CreateSystem,
    MitigateRisk,
)
from aicontrolhub.store import CONTROL_CATALOG, GovernanceError, Store


def create_app(database: str | Path = "runs/aicontrolhub.sqlite3") -> FastAPI:
    store = Store(database)
    app = FastAPI(title="AIControlHub", version="0.1.0")
    web = Path(str(files("aicontrolhub").joinpath("web")))
    app.mount("/assets", StaticFiles(directory=web), name="assets")

    @app.exception_handler(GovernanceError)
    async def governance_error(_, exc: GovernanceError):
        from fastapi.responses import JSONResponse
        message = str(exc)
        code = 404 if message.startswith("unknown system:") or message.startswith(
            "unknown release:"
        ) else 409
        return JSONResponse(status_code=code, content={"detail": message})

    @app.get("/")
    def home():
        return FileResponse(web / "index.html")

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/v1/catalog")
    def catalog():
        return {key: {"function": func, "title": title}
                for key, (func, title) in CONTROL_CATALOG.items()}

    @app.get("/v1/systems")
    def list_systems():
        return store.list_systems()

    @app.post("/v1/systems", status_code=201)
    def create_system(data: CreateSystem):
        return store.create_system(data)

    @app.get("/v1/systems/{system_id}")
    def get_system(system_id: str):
        return store.system(system_id)

    @app.put("/v1/systems/{system_id}/controls/{control_id}")
    def evidence(system_id: str, control_id: str, data: ControlEvidence):
        return store.add_evidence(system_id, control_id, data)

    @app.post("/v1/systems/{system_id}/risks", status_code=201)
    def add_risk(system_id: str, data: CreateRisk):
        return store.add_risk(system_id, data)

    @app.post("/v1/systems/{system_id}/risks/{risk_id}/mitigate")
    def mitigate(system_id: str, risk_id: str, data: MitigateRisk):
        return store.mitigate_risk(system_id, risk_id, data)

    @app.post("/v1/systems/{system_id}/releases", status_code=201)
    def create_release(system_id: str, data: CreateRelease):
        return store.request_release(system_id, data)

    @app.get("/v1/releases/{release_id}/gate")
    def gate(release_id: str):
        return store.gate(release_id)

    @app.post("/v1/releases/{release_id}/approve")
    def approve(release_id: str, data: ApproveRelease):
        return store.approve_release(release_id, data)

    @app.get("/v1/events/verify")
    def verify():
        return store.verify_events()

    return app
