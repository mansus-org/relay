"""The auth endpoints over HTTP, on a real migrated database: get in, come back, stay in."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.contexts.auth.domain.invite import Invite
from relay.main import create_app
from relay.shared.config import Settings

ADA = {"username": "ada_lovelace", "password": "hunter2222", "display_name": "Ada Lovelace"}


@pytest.fixture
async def app(migrated_engine: AsyncEngine, test_settings: Settings) -> AsyncIterator[FastAPI]:
    """An app whose database has the auth tables in it.

    `migrated_engine` is only here for the schema: it runs the same migrations
    against the same file the app is about to open.
    """
    built = create_app(test_settings)
    async with built.router.lifespan_context(built):
        yield built


@pytest.fixture
async def http(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def an_invite(app: FastAPI) -> str:
    """Hand out an invite the way an admin would, until there is an endpoint for it."""
    invite = Invite.issue()
    async with app.state.container.auth_unit_of_work() as uow:
        await uow.invites.add(invite)
        await uow.commit()
    return str(invite.token)


async def a_registration(app: FastAPI, **over: str) -> dict[str, str]:
    """A body that works, with whatever this test wants to change about it."""
    return {"invite_token": await an_invite(app), **ADA} | over


async def register(http: AsyncClient, app: FastAPI, **over: str) -> dict[str, str]:
    response = await http.post("/api/auth/register", json=await a_registration(app, **over))
    assert response.status_code == 201, response.text
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_an_invite_opens_an_account_and_a_session(app: FastAPI, http: AsyncClient) -> None:
    tokens = await register(http, app)

    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in_seconds"] == 900
    assert tokens["access_token"] and tokens["refresh_token"]


async def test_one_invite_opens_exactly_one_account(app: FastAPI, http: AsyncClient) -> None:
    token = await an_invite(app)

    first = await http.post(
        "/api/auth/register", json=await a_registration(app, invite_token=token)
    )
    assert first.status_code == 201

    second = await http.post(
        "/api/auth/register",
        json=await a_registration(
            app,
            invite_token=token,
            username="grace_hopper",
            password="hunter3333",
            display_name="Grace Hopper",
        ),
    )

    assert second.status_code == 403
    assert second.json()["detail"] == "That invite is used."


async def test_an_invite_that_was_never_issued_is_a_404(app: FastAPI, http: AsyncClient) -> None:
    response = await http.post(
        "/api/auth/register", json=await a_registration(app, invite_token="never-handed-out")
    )

    assert response.status_code == 404
    assert "invite" in response.json()["detail"]


async def test_a_username_somebody_already_has_is_a_conflict(
    app: FastAPI, http: AsyncClient
) -> None:
    await register(http, app)

    response = await http.post(
        "/api/auth/register",
        json=await a_registration(app, password="hunter3333", display_name="Other Ada"),
    )

    assert response.status_code == 409
    assert "username" in response.json()["detail"]


@pytest.mark.parametrize(
    ("field", "value", "rule"),
    [
        ("username", "ada lovelace", "Usernames are"),
        ("password", "short", "at least 8"),
        ("display_name", "   ", "cannot be empty"),
    ],
)
async def test_a_registration_that_breaks_a_rule_says_which_one(
    app: FastAPI, http: AsyncClient, field: str, value: str, rule: str
) -> None:
    response = await http.post(
        "/api/auth/register", json=await a_registration(app, **{field: value})
    )

    assert response.status_code == 400
    assert rule in response.json()["detail"]


async def test_the_right_password_opens_a_session(app: FastAPI, http: AsyncClient) -> None:
    await register(http, app)

    response = await http.post("/api/auth/login", json=ADA)

    assert response.status_code == 200
    assert response.json()["access_token"]


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("ada_lovelace", "wrong-password"),
        ("nobody_here", "hunter2222"),
        ("Ada Lovelace", "hunter2222"),
    ],
)
async def test_every_way_in_that_does_not_work_says_the_same_thing(
    app: FastAPI, http: AsyncClient, username: str, password: str
) -> None:
    await register(http, app)

    response = await http.post("/api/auth/login", json={"username": username, "password": password})

    assert response.status_code == 401
    assert response.json()["detail"] == "Username or password is wrong."


async def test_a_token_says_who_it_belongs_to(app: FastAPI, http: AsyncClient) -> None:
    tokens = await register(http, app)

    response = await http.get("/api/auth/me", headers=bearer(tokens["access_token"]))

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "username": "ada_lovelace",
        "display_name": "Ada Lovelace",
        "is_admin": False,
    }


@pytest.mark.parametrize(
    ("scheme", "token"),
    [(None, None), ("Bearer", "not-one-of-ours"), ("Basic", "aGVsbG8=")],
)
async def test_a_call_without_a_token_we_signed_is_401(
    app: FastAPI, http: AsyncClient, scheme: str | None, token: str | None
) -> None:
    headers = {} if scheme is None else bearer(f"{scheme} {token}")

    response = await http.get("/api/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


async def test_a_refresh_token_buys_a_new_pair_and_spends_itself(
    app: FastAPI, http: AsyncClient
) -> None:
    tokens = await register(http, app)

    renewed = await http.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    spent = await http.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert renewed.status_code == 200
    body = renewed.json()
    assert body["refresh_token"] != tokens["refresh_token"]
    assert (await http.get("/api/auth/me", headers=bearer(body["access_token"]))).status_code == 200
    assert spent.status_code == 401


async def test_a_refresh_token_nobody_was_given_is_401(app: FastAPI, http: AsyncClient) -> None:
    response = await http.post("/api/auth/refresh", json={"refresh_token": "made-it-up"})

    assert response.status_code == 401


async def test_register_then_login_then_refresh_then_read_yourself(
    app: FastAPI, http: AsyncClient
) -> None:
    """The whole loop a client goes through, in one test."""
    await register(http, app)

    logged_in = await http.post("/api/auth/login", json=ADA)
    renewed = await http.post(
        "/api/auth/refresh", json={"refresh_token": logged_in.json()["refresh_token"]}
    )

    assert (
        await http.get("/api/auth/me", headers=bearer(renewed.json()["access_token"]))
    ).status_code == 200


async def test_the_first_account_can_come_from_configuration(
    migrated_engine: AsyncEngine, test_settings: Settings
) -> None:
    """An empty Relay has no way in, unless the operator named the first account."""
    settings = test_settings.model_copy(
        update={"admin_username": "root", "admin_password": "hunter2222"}
    )

    built = create_app(settings)
    async with (
        built.router.lifespan_context(built),
        AsyncClient(transport=ASGITransport(app=built), base_url="http://test") as http,
    ):
        logged_in = await http.post("/api/auth/login", json=ADA | {"username": "root"})
        me = await http.get("/api/auth/me", headers=bearer(logged_in.json()["access_token"]))

    assert logged_in.status_code == 200
    assert me.json() == {"id": 1, "username": "root", "display_name": "root", "is_admin": True}


async def test_the_auth_endpoints_are_documented(http: AsyncClient) -> None:
    schema = (await http.get("/openapi.json")).json()

    paths = schema["paths"]
    assert {"/api/auth/register", "/api/auth/login", "/api/auth/refresh", "/api/auth/me"} <= set(
        paths
    )
    assert "409" in paths["/api/auth/register"]["post"]["responses"]
