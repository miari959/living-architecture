"""
FastAPI application entry point.

Serves the JSON API under /api and, when a built frontend exists at
backend/static, serves that SPA for all other routes (single deployable service).

Run with: uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1
(--workers 1 is REQUIRED: the trace lock is per-process.)
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router as api_router

app = FastAPI(title="Living Architecture", version="1.0.0")

# During local dev the Vite dev server runs on another origin; allow it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# Serve the built SPA if present (production single-service mode).
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
_STATIC_DIR = os.path.abspath(_STATIC_DIR)
_INDEX = os.path.join(_STATIC_DIR, "index.html")

if os.path.isdir(_STATIC_DIR) and os.path.exists(_INDEX):
    # Mount hashed assets, and fall back to index.html for client-side routes.
    app.mount("/assets", StaticFiles(directory=os.path.join(_STATIC_DIR, "assets")), name="assets")

    @app.get("/")
    async def _index():
        return FileResponse(_INDEX)

    @app.get("/{full_path:path}")
    async def _spa_fallback(full_path: str):
        # API routes are handled above; anything else serves the SPA shell.
        candidate = os.path.join(_STATIC_DIR, full_path)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(_INDEX)
