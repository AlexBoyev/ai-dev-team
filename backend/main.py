from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router

app = FastAPI(title="AI Dev Team Dashboard")

# API routes (and UI route "/")
app.include_router(router)

# Serve frontend static files
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")