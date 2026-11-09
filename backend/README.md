# Relay backend

The Python (FastAPI) backend of Relay. It replaces the old Go node, and is
built as a SOLID + Domain-Driven Design skeleton: one package
per bounded context, with `api`, `application`, `domain` and `infrastructure`
layers. Today it ships the skeleton, `GET /api/health`, and five contexts.

- `location`: `GET /api/location/postal-code/{postal_code}` turns a Spanish
  postal code into the locality and H3 cell a feed is read from. Galicia only
  for now (`15`, `27`, `32`, `36`), and nothing about the viewer is stored.
- `posts`: `POST /api/posts` says something, `GET /api/feed?cell=<h3>&radius=10`
  reads a locality newest-first, `GET /api/posts/{id}` reads one post. A post
  lives in an H3 resolution-8 cell, or in no locality at all.
  `GET /api/stream?cell=<h3>` is that same locality pushed: the connection stays
  open and every post said within the radius arrives as an `event: post`, with
  the same body the feed carries. Nothing is remembered between connections —
  what was said while you were away is the feed's to give you. Sending a
  `parent_id` answers a post instead of starting one, and
  `GET /api/posts/{id}/replies` reads one level of that thread oldest-first.
  `POST /api/posts/{id}/reactions` leaves an emoji on a post and
  `DELETE /api/posts/{id}/reactions/{emoji}` takes it back; every read carries
  the tallies, and a bearer token on a read only marks which of them were yours.
- `communities`: `GET /api/communities?cell=<h3>` lists the communities whose own
  radius reaches where you are, `POST /api/communities` founds one, `GET
  /api/communities/{id}` reads one, `GET /api/communities/{id}/feed` reads its
  posts (members only), `POST /api/communities/{id}/join` joins it from a cell —
  which is refused if you are standing outside its radius. A member who joined
  under a pseudonym is named by it on that feed and nowhere else.
- `events`: `POST /api/events` plans one, `GET /api/events?cell=<h3>&radius=10`
  reads what is on soonest-first (`from=<date|instant|past>` moves the start),
  `GET /api/events/{id}` reads one with how many are going, `POST
  /api/events/{id}/rsvp` says you are going and `DELETE` the same gives the place
  back. An event is its own row with a time and a place, filed under an H3 cell the
  same way a post is.

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
export SECRET_KEY="$(openssl rand -hex 32)"  # signs every session; see Configuration below
uv run uvicorn relay.main:app --reload   # serve on http://localhost:8000
curl localhost:8000/api/health           # {"status":"ok","version":"dev"} (/health works too)
curl localhost:8000/api/location/postal-code/15001
# {"postal_code":"15001","place_name":"A Coruña","cell":"883925cf43fffff"}
curl 'localhost:8000/api/feed?cell=883925cf43fffff&radius=10'
# {"posts":[],"next_cursor":null} — empty until something is said there
curl -N 'localhost:8000/api/stream?cell=883925cf43fffff'
# an open stream: `event: post` for each post said within 10 km, `: keepalive` while nothing is
curl 'localhost:8000/api/communities?cell=883925cf43fffff'
# [] — every community whose radius reaches that cell; empty until someone founds one
curl 'localhost:8000/api/events?cell=883925cf43fffff&radius=10'
# {"events":[],"next_from":null} — empty until someone plans something
uv run pytest                            # unit, integration, API tests
```

Without `SECRET_KEY` the API says so and refuses to start, because the default
key is published in this repository and anybody could forge a session with it.
`ALLOW_INSECURE_SECRET_KEY=1` runs on that key anyway, on a laptop.

## Accounts, and how the first one happens

An empty database has nobody in it, and there is no open sign-up. Two ways in:

```sh
# 1. The first account, seeded on startup when the database is still empty.
#    Both must be set, or nothing is created.
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
access tokens, and it is not optional any more: while it is still the
development default the API refuses to start, because that key is published in
this repository and anyone could forge a session. On a laptop, say so out loud
with `ALLOW_INSECURE_SECRET_KEY=1`.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./relay.db` | SQLAlchemy URL. `postgresql+asyncpg://user:pass@host/db` switches to Postgres, no code change |
| `SECRET_KEY` | `insecure-dev-secret-change-me` | Signs access tokens. Set it to something long and random (`openssl rand -hex 32`) before anyone connects; the API will not start on the default |
| `ALLOW_INSECURE_SECRET_KEY` | `0` | Start anyway on the development key, and log a warning about it. A laptop only, never a deployment |
| `ADMIN_USERNAME` | unset | Create this account on startup if the database has no users yet. Needs `ADMIN_PASSWORD` |
| `ADMIN_PASSWORD` | unset | Password for `ADMIN_USERNAME`, at least 8 characters |
| `VERSION` | `dev` | Reported by `/health` |
| `LOG_LEVEL` | `INFO` | JSON logs on stdout |
| `WEB_DIST_DIR` | unset | Exported web build to serve at `/` (SPA fallback to `index.html`). Unset = API only |
| `STREAM_KEEPALIVE_SECONDS` | `30` | How long a live stream goes quiet before it sends a keepalive comment. Shorter than whatever sits in front of Relay closes an idle connection for, or the stream drops for nobody at all |

## Web app and combined image

The API lives under `/api`. The Expo app (`mobile/`) also runs in a browser; the
root `Dockerfile` exports it and the backend serves it at `/`, so one image
and one port serve both (this is what runs at relay.mansus.org).

```sh
# from the repo root
docker build -t relay .
docker run --rm -p 8000:8000 -v relay-data:/data \
  -e SECRET_KEY="$(openssl rand -hex 32)" relay
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
