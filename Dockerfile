# Scrum poker: one container, one process. See README.md, "Deploying".

# 1. Build the single-page app.
FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2. A slim Python image serves the page, the API and the room WebSockets.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY app/ app/
RUN pip install . && rm -rf build *.egg-info
COPY --from=frontend /build/dist/ /app/static/

RUN useradd --system --uid 10001 --home-dir /app poker \
    && mkdir /data && chown poker /data
USER poker

# Room definitions live in one SQLite file on this volume. Nothing else is stored.
VOLUME ["/data"]
ENV DATABASE_PATH=/data/scrum-poker.sqlite3 \
    SCRUM_POKER_STATIC_DIR=/app/static
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/healthz', timeout=2)"

# Exactly one worker: live rooms sit in this process's memory.
# The app reads the proxy's headers itself (FORWARDED_ALLOW_IPS), so uvicorn does not.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"$PORT\" --workers 1 --no-proxy-headers --no-server-header"]
