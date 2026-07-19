---
title: Living Architecture
emoji: 🏛️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
license: mit
---

# Living Architecture — Dynamic Trace Explorer

Recover a software system's *real* architecture from its **runtime behaviour**.

This tool runs a target Python application under `sys.settrace()`, captures every
method call, distils the raw trace through a **4-stage filtering pipeline**, and
renders the surviving interactions as a UML sequence diagram. An interactive web
frontend lets you pick a target app, toggle each filter stage, and watch the
architecture emerge from the noise in real time.

Bachelor-thesis project, packaged as a live portfolio piece.

## How it works

```
 target app ──▶ ArchitectureTracer (sys.settrace)  ──▶ raw call events
                                                          │
                          ArchitectureFilter (4 stages)   ▼
   Stage 1  drop libraries & utility calls (fan-in/out)
   Stage 2  limit deep implementation detail (call depth)
   Stage 3  keep only cross-file / cross-class interactions
   Stage 4  classify surviving calls into architectural layers
                                                          │
                          MermaidGenerator                ▼
                                            sequenceDiagram (rendered client-side)
```

The tracing/filtering engine (`src/tracer.py`, `src/filter.py`) is the thesis
core and is treated as frozen. The web layer wraps it without changing any
tracing or filtering behaviour.

## Architecture

- **`src/`** — the engine: `tracer.py`, `filter.py`, `visualizer.py` (PlantUML,
  original CLI path), and `mermaid_visualizer.py` (web path).
- **`backend/`** — FastAPI app. `app/runners/` wraps each target app; `app/core/`
  serializes trace execution behind a per-process lock; `app/api/` exposes the
  JSON API; `app/main.py` also serves the built SPA.
- **`frontend/`** — React + Vite SPA (Mermaid.js diagrams), builds into
  `backend/static`.
- **`applications/`** — the 8 target apps (3 hand-crafted console demos + 5
  real-world/representative apps).

## Run locally

Backend (Python 3.13):

```bash
python -m venv .venv && source .venv/bin/activate
pip install --no-deps -r backend/requirements.txt
uvicorn backend.app.main:app --port 8000 --workers 1   # --workers 1 is required
```

Frontend (dev, with hot reload — proxies /api to :8000):

```bash
cd frontend && npm install && npm run dev      # http://localhost:5173
```

Or build the SPA and let the backend serve everything on one port:

```bash
cd frontend && npm run build                   # outputs to backend/static
# then open http://localhost:8000
```

> **`--workers 1` is mandatory.** `sys.settrace()` is process-global and only one
> trace may run at a time; the backend enforces this with a single in-process lock.

## Deploy (Render)

The repo includes a `Dockerfile` and a `render.yaml` blueprint.

1. Push this repo to GitHub.
2. In Render: **New → Blueprint**, connect the repo. Render reads `render.yaml`
   and provisions a Docker web service (free plan, health check `/api/health`).
3. First build installs the Python deps and builds the SPA in-image; the
   `.dockerignore` keeps vendored `.git`/tests/the unused Zulip server tree out of
   the build context.

Any Docker host works too:

```bash
docker build -t living-architecture .
docker run -p 8000:8000 living-architecture
```

## Notes on the target apps

- **Console demos & Home Assistant** exercise their logic at a traceable level, so
  Stage 4 recovers clean architecture.
- **Flask / Django (RealWorld)** run their full HTTP request stack; their story is
  the dramatic Stage 0 → Stage 4 *reduction* rather than a tidy final diagram.
- **FastAPI** is a compact purpose-built layered demo (`applications/fastapi_demo`).
  The vendored RealWorld FastAPI clone needs FastAPI ~0.79 + Pydantic v1, which
  cannot coexist with the modern FastAPI the backend itself uses.
