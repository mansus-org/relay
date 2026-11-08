# Relay backend

The Python (FastAPI) backend of Relay. It replaces the old Go node, and is
built as a SOLID + Domain-Driven Design skeleton: one package
per bounded context, with `api`, `application`, `domain` and `infrastructure`
layers. Today it ships the skeleton, `GET /api/health`, and two contexts.

`location`: `GET /api/location/postal-code/{postal_code}` turns a Spanish postal
code into the locality and H3 cell a feed is read from. Galicia only for now
(`15`, `27`, `32`, `36`), and nothing about the viewer is stored.

`auth` is the door:

| Endpoint | Takes | Gives you |
|---|---|---|
| `POST /api/auth/register` | an invite token, a username, a password, a display name | an account and a session |
| `POST /api/auth/login` | username and password | a session |
| `POST /api/auth/refresh` | a refresh token | a new session, the old one spent |
| `GET /api/auth/me` | a bearer access token | whose account it is |

Relay is invite-only: an invite is spent by the first person who registers with
it, and wrong username and wrong password get the same answer, so login cannot be
used to find out which accounts exist.

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

## Accounts, and how the first one happens

An empty database has nobody in it, and there is no open sign-up. Two ways in:

```sh
# 1. The first account, seeded on startup when the database is still empty.
#    Both must be set, or nothing is created. Set SECRET_KEY too, before anyone else connects.
ADMIN_USERNAME=you ADMIN_PASSWORD='at-least-8-characters' uv run uvicorn relay.main:app --reload
curl -X POST localhost:8000/api/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"you","password":"at-least-8-characters"}'

# 2. Everyone after that needs an invite. Minting one is still a database job
#    (an endpoint for it is the next ticket); with SQLite:
sqlite3 relay.db "insert into invites (token) values ('$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')')"
curl -X POST localhost:8000/api/auth/register \
  -H 'content-type: application/json' \
  -d '{"invite_token":"<that token>","username":"someone","password":"...","display_name":"Someone"}'
```

The access token is a signed JWT, good for 15 minutes. The refresh token is a
random string kept in the database as a fingerprint, good for 30 days and for
one use: `/auth/refresh` hands back a new pair and spends the old one, so a
stolen token is caught the moment its owner uses it. `SECRET_KEY` signs the
access tokens; while it is still the development default, startup logs a warning.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./relay.db` | SQLAlchemy URL. `postgresql+asyncpg://user:pass@host/db` switches to Postgres, no code change |
| `SECRET_KEY` | `insecure-dev-secret-change-me` | Signs access tokens. Set it to something long and random before anyone connects; startup warns while it is the default |
| `ADMIN_USERNAME` | unset | Create this account on startup if the database has no users yet. Needs `ADMIN_PASSWORD` |
| `ADMIN_PASSWORD` | unset | Password for `ADMIN_USERNAME`, at least 8 characters |
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
