"""
RootTrace Main FastAPI Application.
Serves the REST API and the incident response dashboard frontend.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os

from .api.routes import router as api_router

app = FastAPI(
    title="RootTrace — Autonomous Incident Investigation & Recovery",
    description="Evidence-driven autonomous software-incident investigation and verified-recovery system.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# Mount frontend dist (React app) or fallback to static
dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "static"))

if os.path.exists(os.path.join(dist_dir, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, "assets")), name="assets")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def serve_index():
    react_index = os.path.join(dist_dir, "index.html")
    if os.path.exists(react_index):
        return FileResponse(react_index)

    static_index = os.path.join(static_dir, "index.html")
    if os.path.exists(static_index):
        return FileResponse(static_index)

    return {
        "status": "RootTrace API Online",
        "docs_url": "/docs",
        "endpoints": ["/api/scenarios", "/api/incident", "/api/system/status"]
    }
