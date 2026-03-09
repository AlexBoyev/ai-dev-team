from threading import Thread

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from backend.core.memory import get_run_in_progress, reset_state, snapshot_for_api
from backend.core.orchestrator import demo_run

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


class RunRequest(BaseModel):
    repo_url: str | None = None


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/api/state")
def api_state():
    return JSONResponse(snapshot_for_api())


@router.post("/api/run")
def api_run(payload: RunRequest | None = None):
    if get_run_in_progress():
        return JSONResponse({"ok": True, "status": "already_running"})

    repo_url = None
    if payload is not None:
        repo_url = (payload.repo_url or "").strip() or None

    Thread(target=demo_run, kwargs={"repo_url": repo_url}, daemon=True).start()
    return JSONResponse({"ok": True, "status": "started"})


@router.post("/api/reset")
def api_reset():
    reset_state()
    return JSONResponse({"ok": True})