# Backend development

How the Python backend in [`backend/`](../backend/) is built and how to extend
it. It replaces the old Go node; today it ships the
skeleton, `GET /api/health`, the `auth` context (`/api/auth/register`, `/login`,
`/refresh`, `/me`), the `location` context (postal code to H3 cell),
the `posts` context (say something, read a locality's feed), the
`communities` context (groups with a locality, their feed and their joins) and
the `events` context (what is on where and when, and saying you are going).
Quickstart: [`backend/README.md`](../backend/README.md).

Everything runs through [uv](https://docs.astral.sh/uv/): `uv sync`,
`uv run pytest`, `uv run alembic upgrade head`,
`uv run uvicorn relay.main:app`. There is no `requirements.txt` and no pip.
Pydantic v2 is the modelling basis: settings, domain entities and value
objects and API schemas.

## Architecture

SOLID + Domain-Driven Design, one package per bounded context. Dependencies point
inward:

```
api  →  application  →  domain  ←  infrastructure
```

| Layer | Holds | May import |
|---|---|---|
| `domain` | Entities, value objects, aggregates, domain events, domain services, repository interfaces (`abc.ABC`) | Pydantic, stdlib. Never FastAPI or SQLAlchemy |
| `application` | Application services (one small class per operation), the `UnitOfWork` ABC and `Clock`. They return domain objects | domain. Never FastAPI or SQLAlchemy |
| `infrastructure` | SQLAlchemy ORM models, concrete repositories and `UnitOfWork`, external clients | domain, application. ORM models never leave this layer |
| `api` | FastAPI routers, Pydantic request/response schemas that map domain objects, `Depends` providers. Thin | application (and the container) |

Cross-cutting pieces live in `relay.shared`: `config` (Settings), `logging`
(JSON), and shared base classes in each layer package. The layer rules are
enforced by import-linter contracts in `backend/pyproject.toml`
(`uv run lint-imports`), so a wrong-direction import fails CI.

### Adding a bounded context

Create `backend/src/relay/contexts/<name>/` with the same four packages:

```
contexts/posts/
  domain/          # Post entity, PostRepository (ABC)
  application/     # CreatePost application service, PostsUnitOfWork (ABC)
  infrastructure/  # PostModel (ORM), SqlAlchemyPostRepository, unit of work
  api/             # router, request/response schemas, providers
```

That one is not an example: `contexts/posts/` is there and is the context to
copy when adding another. `contexts/communities/` is a second one, and the one to
look at when the new context has more than one table, or needs to read another
context's table: its feed query reaches into `posts`' ORM model, one-way, because
teaching `posts` about communities would point the dependency the wrong way.
`contexts/events/` is a third, and the one to look at when the new context asks
the same questions of H3 that `posts` does: it answers them for itself instead of
importing `posts`' helpers, so that changing how far a listing reaches is never
also a change to what is on.

Then: add the layers to the import-linter contracts, import the ORM models in
`migrations/env.py` (so autogenerate sees them), create a migration
(`uv run alembic revision --autogenerate -m "posts"`), add a `get_<service>()`
method to the `Container`, and include the router in `create_app`.

A context that answers from a shipped dataset instead of a database (`location`
does this) skips the ORM model, the migration and the unit of work: `domain` and
`application` are built the same way, `infrastructure` loads the file, and the
layer contracts still apply. `scripts/build_postal_codes.py` regenerates that
dataset from its source, and the source licence goes in the data file header and
in the OpenAPI operation.

A context that guards traffic exposes exactly one door for the others to borrow,
and everything else stays private. `auth` publishes
`relay.contexts.auth.api.dependencies.CurrentUser` (a `Depends` on
`get_current_user`): any router that needs to know who is calling asks for
`user: CurrentUser` and gets the account or a 401, without importing anything
else from auth. Post, community and moderation contexts will protect their
routes the same way.

## Dependency injection

Constructor injection throughout.

- Every application service, repository and unit of work receives its
  collaborators in `__init__`. No module-level singletons, no service locator,
  no `Settings()` inside classes.
- Classes depend on abstract base classes (`abc.ABC`) from domain/application,
  never on concrete
  infrastructure classes.
- `relay/main.py` is the single composition root. `create_app(settings)` takes
  config as an argument; the lifespan builds the engine and session factory
  once, stores a `Container` (plain class, `relay/container.py`) on
  `app.state`, and disposes the engine on shutdown. The module-level `app`
  that uvicorn serves is `create_app(Settings())`.
- FastAPI `Depends` appears only in `api/` packages, as thin providers that ask
  the container for a built application service.

```python
class CreatePost:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None: ...
    async def execute(self, author_id: UserId, body: str) -> Post: ...
```

Application services return domain objects (entities or value objects), not
separate transfer types. The `api` layer maps them into its Pydantic response
schemas (for example `HealthResponse.from_domain(HealthStatus)`), so the domain
never knows about HTTP. Repositories are `abc.ABC` classes in `domain`; each
context's repository subclasses the generic base `Repository[E, ID]`
(`relay.shared.domain`, abstract `get` and `add`) and adds its own queries. The
`UnitOfWork` ABC lives in `application` so tests can use `FakeUnitOfWork`, and
infrastructure provides the concrete SQLAlchemy implementation. `Clock` is a
plain class with `now()`; tests pass a `FixedClock` subclass.

## Testing

`uv run pytest` (pytest-asyncio in auto mode). Shared fixtures are in
`tests/conftest.py`, fakes in `tests/fakes/`.

| Folder | What | How |
|---|---|---|
| `tests/unit/` | Domain and application | No DB, no FastAPI. In-memory fakes (`FakeUnitOfWork`, `InMemory<X>Repository`, `FixedClock`) passed to constructors |
| `tests/integration/` | Repositories and unit of work against a real DB | SQLite by default; the same tests run on Postgres when `TEST_DATABASE_URL` is set. The schema comes from `alembic upgrade head`, never `create_all` |
| `tests/api/` | HTTP behaviour | `httpx.AsyncClient` + `ASGITransport` against `create_app(test_settings)`. Override providers with `app.dependency_overrides` |
| import-linter | Architecture | Contracts in `pyproject.toml` (`uv run lint-imports`) |

To run the Postgres paths locally:

```sh
docker run -d --name relay-pg -e POSTGRES_USER=relay -e POSTGRES_PASSWORD=relay \
  -e POSTGRES_DB=relay_test -p 5432:5432 postgres:17-alpine
TEST_DATABASE_URL=postgresql+asyncpg://relay:relay@localhost:5432/relay_test uv run pytest
```

## Lint, types, pre-commit

```sh
uv run ruff check            # E, W, F, I, B, UP, SIM, ASYNC, S, N, RUF
uv run ruff format --check   # the only formatter (line length 100)
uv run ty check              # src/ and tests/; no mypy
uv run lint-imports
```

Config is in `backend/pyproject.toml`. `S101` (assert) is allowed under
`tests/`.

The root `.pre-commit-config.yaml` runs these for files under `backend/`
(ruff check `--fix`, ruff format, `uv lock`, ty, lint-imports):

```sh
uv tool install pre-commit
pre-commit install
pre-commit run --all-files
```

Change dependencies with `uv add <pkg>` (or `uv add --dev <pkg>`); commit
`uv.lock`. CI installs with `uv sync --frozen`.

## Configuration

Read once into `Settings` (pydantic-settings) in `main.py`.

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./relay.db` | Selects the driver. `postgresql+asyncpg://user:pass@host/db` switches to Postgres with no code change. Plain `sqlite://` and `postgresql://` get the async driver added |
| `VERSION` | `dev` | Reported by `/api/health`; the Docker build arg sets it |
| `WEB_DIST_DIR` | unset | Directory with the exported web build. When set, it is served at `/` with SPA fallback; unset (dev, tests) serves the API only |
| `LOG_LEVEL` | `INFO` | Logs are one JSON object per line on stdout |
| `TEST_DATABASE_URL` | unset | Tests only. When set, integration tests use it instead of a temp SQLite file |
| `SECRET_KEY` | `insecure-dev-secret-change-me` | Signs the access tokens. Set it before anyone connects (`openssl rand -hex 32`): the default is published in this repository, so the API refuses to start while it is still in place |
| `ALLOW_INSECURE_SECRET_KEY` | `0` | Start on the development key anyway, and log a warning. For a laptop, never a deployment |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | unset | Bootstrap: create this account on startup when the database has no users yet. Both must be set; the password is at least 8 characters. Unset means a fresh database stays invite-only |

Migrations: `uv run alembic upgrade head` (reads `DATABASE_URL`).

## Docker image

The root `Dockerfile` builds the backend together with the Expo web export (see
the "Web app and combined image" section of `backend/README.md`).

```sh
docker build -t relay --build-arg VERSION=dev .
docker run -d --name relay -p 8000:8000 -v relay-data:/data \
  -e SECRET_KEY="$(openssl rand -hex 32)" relay
curl localhost:8000/api/health   # migrations ran on start
```

Multi-stage build: the Expo web export, `uv sync --frozen --no-dev` for the
backend, and a slim Python runtime stage that runs as an unprivileged user
(uid 100, gid 101) with a `HEALTHCHECK` on `/api/health`. SQLite lives in the `/data`
volume; set `DATABASE_URL` for Postgres.

`docker-compose.yml` runs that same image: it builds it, keeps SQLite in a named
volume, takes its environment from `.env` (copy `.env.example`), and carries the
Postgres swap in `docker-compose.override.yml.example`. The steps are in the root
README. The AI moderation sidecar in the compose file is a profile, off unless you
ask for it, and it decides no model: that is RELY-102.

CI: `.github/workflows/backend-test.yml` runs the gates above (pytest on
SQLite, then on a Postgres service container). `.github/workflows/deploy.yml`
builds the root image and pushes it to `ghcr.io/mansus-org/relay`
(`sha-*` + `latest` on main, `pr-<n>-<sha>` for pull requests).
