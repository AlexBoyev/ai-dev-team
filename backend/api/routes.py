from threading import Thread

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from backend.core.memory import snapshot_for_api, reset_state, get_run_in_progress
from backend.core.orchestrator import demo_run

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/api/state")
def api_state():
    return JSONResponse(snapshot_for_api())


@router.post("/api/run")
def api_run():
    # better UX: tell the UI if it's already running
    if get_run_in_progress():
        return JSONResponse({"ok": True, "status": "already_running"})

    Thread(target=demo_run, daemon=True).start()
    return JSONResponse({"ok": True, "status": "started"})


@router.post("/api/reset")
def api_reset():
    reset_state()
    return JSONResponse({"ok": True})