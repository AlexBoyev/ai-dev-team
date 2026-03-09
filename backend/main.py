from __future__ import annotations
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from backend.api.routes import router

app = FastAPI(title="AI Dev Team Dashboard")
app.include_router(router)
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
