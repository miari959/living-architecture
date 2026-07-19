# ============================================================================
# Stage 1 — build the React SPA. The repo layout is mirrored (/app/frontend +
# /app/backend) so vite's outDir ("../backend/static") resolves correctly.
# ============================================================================
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build            # writes to /app/backend/static

# ============================================================================
# Stage 2 — Python runtime. Matches the interpreter the venv was verified on.
# ============================================================================
FROM python:3.13-slim AS runtime

WORKDIR /app

# Install Python deps (the complete, pinned freeze -> --no-deps). build-essential
# is added for any package lacking a prebuilt wheel, then removed in the SAME
# layer so it doesn't bloat the final image.
COPY backend/requirements.txt ./backend/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && pip install --no-cache-dir --no-deps -r backend/requirements.txt \
    && apt-get purge -y build-essential \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# --- application code (engine + backend) ---
COPY src/ ./src/
COPY backend/ ./backend/

# --- target apps: explicit allowlist so only what runs enters the image ---
# (applications/ is a PEP 420 namespace package — no __init__.py needed)
COPY applications/console_app_1_sorter/ ./applications/console_app_1_sorter/
COPY applications/console_app_2/ ./applications/console_app_2/
COPY applications/console_app_3/ ./applications/console_app_3/
COPY applications/fastapi_demo/ ./applications/fastapi_demo/
COPY applications/external_flask/ ./applications/external_flask/
COPY applications/external_django/ ./applications/external_django/
# Home Assistant: only the package folder (the rest is excluded via .dockerignore)
COPY applications/external_homeassistant/homeassistant/ ./applications/external_homeassistant/homeassistant/

# --- built SPA from stage 1 ---
COPY --from=frontend /app/backend/static ./backend/static

# Render/other PaaS inject $PORT; default to 8000 locally.
ENV PORT=8000
EXPOSE 8000

# --workers 1 is REQUIRED: the trace lock (and sys.settrace) are per-process.
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
