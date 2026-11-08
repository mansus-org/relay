# syntax=docker/dockerfile:1

# Relay: the FastAPI backend serving the Expo web build, one image, one port.
#
#   docker build -t relay .
#   docker run -d -p 8000:8000 -v relay-data:/data -e SECRET_KEY="$(openssl rand -hex 32)" relay
#
# SECRET_KEY signs every session and the API will not start without one: the
# default is published in this repository. On a laptop,
# -e ALLOW_INSECURE_SECRET_KEY=1 runs on the default anyway.
# http://localhost:8000/ is the web app, /api/* the API (/api/health for probes).
# Runs as uid 100 / gid 101, the old Go image's user, so the existing data disk
# stays writable. Migrations run on start. /data holds the SQLite database; set
# DATABASE_URL=postgresql+asyncpg://... to use Postgres instead.

# ---------- Stage 1: export the Expo web build ----------
FROM node:22-slim AS web
WORKDIR /src/mobile
COPY mobile/package.json mobile/package-lock.json ./
RUN npm ci
COPY mobile/ ./
RUN npx expo export --platform web --output-dir /web-dist

# ---------- Stage 2: resolve and install locked backend dependencies ----------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first so this layer is cached until the lockfile changes.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version backend/README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY backend/src/ ./src/
COPY backend/alembic.ini ./
COPY backend/migrations/ ./migrations/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------- Stage 3: runtime ----------
FROM python:3.13-slim-bookworm
ARG VERSION=dev
ENV VERSION=${VERSION} \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite+aiosqlite:////data/relay.db \
    WEB_DIST_DIR=/app/web

RUN groupadd --system --gid 101 relay \
    && useradd --system --uid 100 --gid relay --home-dir /app relay \
    && mkdir /data && chown relay:relay /data
WORKDIR /app
COPY --from=build --chown=relay:relay /app /app
COPY --from=web --chown=relay:relay /web-dist /app/web

USER relay
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"]

# Migrate (alembic reads DATABASE_URL), then serve. exec keeps uvicorn as PID 1 for signals.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn relay.main:app --host 0.0.0.0 --port 8000"]
