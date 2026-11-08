# Relay backend

The Python (FastAPI) backend of Relay. It replaces the old Go node, and is
built as a SOLID + Domain-Driven Design skeleton: one package
per bounded context, with `api`, `application`, `domain` and `infrastructure`
layers. Today it ships the skeleton, `GET /api/health`, and the `location`
context: `GET /api/location/postal-code/{postal_code}` turns a Spanish postal
code into the locality and H3 cell a feed is read from. Galicia only for now
(`15`, `27`, `32`, `36`), and nothing about the viewer is stored.

The architecture, testing plan and tooling are in
[`docs/backend-development.md`](../docs/backend-development.md).

## Prerequisites

[uv](https://docs.astral.sh/uv/) only. It installs Python (see `.python-version`),
the virtualenv and the locked dependencies.

## Quickstart

Run everything from `backend/`:

```sh
uv sync                                  # install Python + dependencies
uv run alembic upgrade head              # create/upgrade the SQLite database
uv run uvicorn relay.main:app --reload   # serve on http://localhost:8000
curl localhost:8000/api/health           # {"status":"ok","version":"dev"} (/health works too)
curl localhost:8000/api/location/postal-code/15001
# {"postal_code":"15001","place_name":"A Coruña","cell":"883925cf43fffff"}
uv run pytest                            # unit, integration, API tests
```

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./relay.db` | SQLAlchemy URL. `postgresql+asyncpg://user:pass@host/db` switches to Postgres, no code change |
| `VERSION` | `dev` | Reported by `/health` |
| `LOG_LEVEL` | `INFO` | JSON logs on stdout |
| `WEB_DIST_DIR` | unset | Exported web build to serve at `/` (SPA fallback to `index.html`). Unset = API only |

## Web app and combined image

The API lives under `/api`. The Expo app (`mobile/`) also runs in a browser; the
root `Dockerfile` exports it and the backend serves it at `/`, so one image
and one port serve both (this is what runs at relay.mansus.org).

```sh
# from the repo root
docker build -t relay .
docker run --rm -p 8000:8000 -v relay-data:/data relay
# http://localhost:8000/        web app (deep links like /login work)
# http://localhost:8000/api/health
```

Without Docker: `cd mobile && npx expo export --platform web`, then
`WEB_DIST_DIR=../mobile/dist uv run uvicorn relay.main:app` from `backend/`.

## Checks

```sh
uv run ruff check && uv run ruff format --check
uv run ty check
uv run lint-imports
uv run pytest
```
