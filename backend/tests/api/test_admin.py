"""The admin API over HTTP on a migrated database: the queue, the accounts, the invites.

Every route here belongs to an account, so the first test of each group is the one that
says a member cannot get in. Everything else is what the three tables record and what
they refuse to record.

The clock steps, so a test can put two things in a row and know which came first.
"""

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.contexts.admin.api.admin import join_invite_link
from relay.contexts.admin.domain.moderation_log import ModerationLog
from relay.contexts.auth.domain.invite import Invite
from relay.contexts.auth.infrastructure.models import UserRow
from relay.main import create_app
from relay.shared.config import Settings
from tests.fakes.clock import SteppingClock

# The account the app creates on a fresh database. It is the only admin in this file,
# which is what makes "you cannot deactivate yourself" testable without a second one.
ADMIN = {"username": "root_admin", "password": "hunter2222"}

# The placeholder identity the posts API still takes as a bearer token (RELY-04). Posts
# are not attributed to accounts until RELY-87, so this is how a post gets made here.
AUTHOR = UUID("11111111-1111-1111-1111-111111111111")

# One path per table, for the tests that only ask whether the door is shut.
A_TABLE = [
    "/api/admin/queue",
    "/api/admin/log",
    "/api/admin/members",
    "/api/admin/invites",
]

# Where this Relay is meant to be found, so an invite can be turned into a link to send.
SITE = "relay.example.org"


@pytest.fixture
def admin_settings(database_url: str) -> Settings:
    """The suite's settings, plus the operator's first account and where the site lives."""
    return Settings(
        database_url=database_url,
        version="test",
        allow_insecure_secret_key=True,
        admin_username=ADMIN["username"],
        admin_password=ADMIN["password"],
        invite_base_url=SITE,
    )


@pytest.fixture
async def app(migrated_engine: AsyncEngine, admin_settings: Settings) -> AsyncIterator[FastAPI]:
    """An app on the migrated database, with the first admin seeded by its own startup."""
    built = create_app(admin_settings)
    async with built.router.lifespan_context(built):
        built.state.container.clock = SteppingClock()
        yield built


@pytest.fixture
async def http(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
async def admin(http: AsyncClient) -> dict[str, str]:
    """Headers for the seeded admin, which is how every admin call here starts."""
    response = await http.post("/api/auth/login", json=ADMIN)
    assert response.status_code == 200, response.text
    return bearer(response.json()["access_token"])


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def an_account(http: AsyncClient, app: FastAPI, username: str, display_name: str) -> dict:
    """A registered account with its tokens. Relay is invite-only, so this mints the invite too."""
    invite = Invite.issue()
    async with app.state.container.auth_unit_of_work() as uow:
        await uow.invites.add(invite)
        await uow.commit()
    response = await http.post(
        "/api/auth/register",
        json={
            "invite_token": str(invite.token),
            "username": username,
            "password": "hunter2222",
            "display_name": display_name,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def say(http: AsyncClient, body: str) -> dict:
    """A post, said as the placeholder identity the posts API still takes."""
    response = await http.post("/api/posts", json={"body": body}, headers=bearer(str(AUTHOR)))
    assert response.status_code == 201, response.text
    return response.json()


async def machine_flags(app: FastAPI, post_id: str, verdict: str) -> None:
    """Stand in for a classifier: a verdict left on a post, and no decision made.

    Nothing runs a model here yet, so this writes the one log line one would have left.
    The queue and the trail are what is under test, not the opinion in them.
    """
    container = app.state.container
    async with container.moderation_unit_of_work() as uow:
        post = await uow.posts.get(UUID(post_id))
        assert post is not None
        await uow.log.add(
            ModerationLog.flagged_by_machine(
                post=post,
                decision={"verdict": verdict, "confidence": 0.91},
                created_at=container.clock.now(),
            )
        )
        await uow.commit()


async def decide(
    http: AsyncClient, admin: dict[str, str], post_id: str, verdict: str, **body: Any
) -> Any:
    """One decision, made the way the admin screen makes it: a verb on the post."""
    return await http.post(f"/api/admin/queue/{post_id}/{verdict}", json=body, headers=admin)


async def the_admin_id(http: AsyncClient, admin: dict[str, str]) -> int:
    page = (await http.get("/api/admin/members?admin=true", headers=admin)).json()
    return page["members"][0]["id"]


# --- who is allowed in ----------------------------------------------------------------


async def test_nobody_gets_in_without_a_session(http: AsyncClient) -> None:
    for path in A_TABLE:
        assert (await http.get(path)).status_code == 401, path


async def test_a_member_is_not_an_admin(http: AsyncClient, app: FastAPI) -> None:
    member = await an_account(http, app, "ada_lovelace", "Ada Lovelace")
    headers = bearer(member["access_token"])
    for path in A_TABLE:
        assert (await http.get(path, headers=headers)).status_code == 403, path
    # The writes are the same door. A member who can only read the queue can still
    # do nothing with it, which is the point.
    assert (await http.post("/api/admin/invites", json={}, headers=headers)).status_code == 403
    post = await say(http, "I would like to moderate this myself")
    assert (await decide(http, headers, post["id"], "approve")).status_code == 403


async def test_a_stolen_look_at_the_queue_needs_a_real_token(http: AsyncClient) -> None:
    assert (await http.get("/api/admin/queue", headers=bearer("not-a-token"))).status_code == 401


# --- the queue ------------------------------------------------------------------------


async def test_a_new_post_waits_in_the_queue(http: AsyncClient, admin: dict[str, str]) -> None:
    post = await say(http, "Someone is parking in the bike lane again")
    page = (await http.get("/api/admin/queue", headers=admin)).json()

    assert page["total"] == 1
    shown = page["posts"][0]
    assert shown["id"] == post["id"]
    assert shown["body"] == "Someone is parking in the bike lane again"
    assert shown["author_id"] == str(AUTHOR)
    assert shown["moderation_status"] == "pending"


async def test_the_queue_shows_one_state_at_a_time(
    http: AsyncClient, admin: dict[str, str]
) -> None:
    kept = await say(http, "Flea market on Saturday, bring boxes")
    gone = await say(http, "Buy my pills, cheap, no questions")
    await decide(http, admin, kept["id"], "approve")
    await decide(http, admin, gone["id"], "remove", reason="Selling medicine")

    for state, expected in {
        "pending": [],
        "approved": [kept["id"]],
        "removed": [gone["id"]],
    }.items():
        page = (await http.get(f"/api/admin/queue?status={state}", headers=admin)).json()
        assert [post["id"] for post in page["posts"]] == expected, state
        assert page["total"] == len(expected)

    # With no filter at all the queue is the work left, and all of this is dealt with.
    assert (await http.get("/api/admin/queue", headers=admin)).json()["posts"] == []


async def test_one_post_can_be_read_whatever_state_it_is_in(
    http: AsyncClient, admin: dict[str, str]
) -> None:
    post = await say(http, "A post that will not last")
    await decide(http, admin, post["id"], "remove", reason="Advertising")

    seen = await http.get(f"/api/admin/queue/{post['id']}", headers=admin)
    assert seen.status_code == 200
    assert seen.json()["moderation_status"] == "removed"
    # The public read treats it as gone, which is the whole effect of removing one.
    assert (await http.get(f"/api/posts/{post['id']}")).status_code == 404
    assert (await http.get(f"/api/admin/queue/{uuid4()}", headers=admin)).status_code == 404


async def test_the_queue_pages(http: AsyncClient, admin: dict[str, str]) -> None:
    ids = {(await say(http, f"Post number {n}"))["id"] for n in range(3)}

    first = (await http.get("/api/admin/queue?limit=2", headers=admin)).json()
    rest = (await http.get("/api/admin/queue?limit=2&offset=2", headers=admin)).json()

    assert first["total"] == 3 and rest["total"] == 3
    assert len(first["posts"]) == 2 and len(rest["posts"]) == 1
    seen = {post["id"] for post in first["posts"]} | {post["id"] for post in rest["posts"]}
    assert seen == ids


async def test_a_page_size_somebody_cannot_have_meant_is_refused(
    http: AsyncClient, admin: dict[str, str]
) -> None:
    assert (await http.get("/api/admin/queue?limit=0", headers=admin)).status_code == 422
    assert (await http.get("/api/admin/members?limit=500", headers=admin)).status_code == 422


async def test_what_a_machine_thought_travels_with_the_post(
    http: AsyncClient, app: FastAPI, admin: dict[str, str]
) -> None:
    flagged = await say(http, "Buy my pills, cheap, no questions")
    await machine_flags(app, flagged["id"], "spam")
    plain = await say(http, "Flea market on Saturday, bring boxes")

    page = (await http.get("/api/admin/queue", headers=admin)).json()["posts"]
    by_id = {post["id"]: post for post in page}
    assert by_id[flagged["id"]]["ai_decision"] == {"verdict": "spam", "confidence": 0.91}
    # A post nobody ran through it carries no opinion at all, rather than an empty one.
    assert by_id[plain["id"]]["ai_decision"] is None
    # And the model flagged it; it did not decide it. It is still the admin's to settle.
    assert by_id[flagged["id"]]["moderation_status"] == "pending"

    entry = (await http.get("/api/admin/log", headers=admin)).json()["entries"][0]
    assert entry["action"] == "flagged"
    assert entry["trigger"] == "ai"
    assert entry["actor_id"] is None  # a model has no account to be blamed with
    assert entry["ai_decision"] == {"verdict": "spam", "confidence": 0.91}

    # The person who finishes it is still recorded as a person.
    await decide(http, admin, flagged["id"], "remove", reason="Spam")
    newest = (await http.get("/api/admin/log", headers=admin)).json()["entries"][0]
    assert newest["trigger"] == "human"


# --- reviewing ------------------------------------------------------------------------


async def test_approving_takes_a_post_out_of_the_queue(
    http: AsyncClient, admin: dict[str, str]
) -> None:
    post = await say(http, "Lost cat, orange, near the market")

    answer = await decide(http, admin, post["id"], "approve")

    assert answer.status_code == 200, answer.text
    assert answer.json()["moderation_status"] == "approved"
    assert (await http.get("/api/admin/queue", headers=admin)).json()["total"] == 0
    # Approving changes nothing about whether it can be read: Relay shows everything
    # that has not been removed, so it was readable before and is readable now.
    assert (await http.get(f"/api/posts/{post['id']}")).status_code == 200


async def test_removing_needs_a_reason(http: AsyncClient, admin: dict[str, str]) -> None:
    post = await say(http, "Sell your account credentials to me")

    assert (await decide(http, admin, post["id"], "remove")).status_code == 400
    assert (await decide(http, admin, post["id"], "remove", reason="   ")).status_code == 400
    # Neither one decided anything.
    seen = (await http.get(f"/api/admin/queue/{post['id']}", headers=admin)).json()
    assert seen["moderation_status"] == "pending"

    answer = await decide(http, admin, post["id"], "remove", reason="Asking for credentials")
    assert answer.json()["moderation_status"] == "removed"


async def test_a_reason_longer_than_a_reason_is_refused(
    http: AsyncClient, admin: dict[str, str]
) -> None:
    post = await say(http, "A post")
    answer = await decide(http, admin, post["id"], "remove", reason="n" * 501)
    assert answer.status_code == 400


async def test_restoring_puts_a_post_back_as_approved(
    http: AsyncClient, admin: dict[str, str]
) -> None:
    post = await say(http, "A post that was taken down by mistake")
    await decide(http, admin, post["id"], "remove", reason="Looked like spam")

    answer = await decide(http, admin, post["id"], "restore")

    assert answer.status_code == 200, answer.text
    assert answer.json()["moderation_status"] == "approved"
    assert (await http.get(f"/api/posts/{post['id']}")).status_code == 200


async def test_a_decision_that_was_already_made_is_a_conflict(
    http: AsyncClient, admin: dict[str, str]
) -> None:
    post = await say(http, "One post, several wrong questions")

    assert (await decide(http, admin, post["id"], "approve")).status_code == 200
    assert (await decide(http, admin, post["id"], "approve")).status_code == 409
    assert (await decide(http, admin, post["id"], "restore")).status_code == 409

    assert (
        await decide(http, admin, post["id"], "remove", reason="Changed my mind")
    ).status_code == 200
    assert (await decide(http, admin, post["id"], "remove", reason="Again")).status_code == 409
    assert (await decide(http, admin, post["id"], "approve")).status_code == 409


async def test_reviewing_a_post_that_is_not_there(http: AsyncClient, admin: dict[str, str]) -> None:
    assert (await decide(http, admin, str(uuid4()), "approve")).status_code == 404


# --- the trail ------------------------------------------------------------------------


async def test_every_decision_leaves_a_line(http: AsyncClient, admin: dict[str, str]) -> None:
    admin_id = await the_admin_id(http, admin)
    kept = await say(http, "Road closed on Tuesday")
    gone = await say(http, "Free money, click now")
    await decide(http, admin, kept["id"], "approve")
    await decide(http, admin, gone["id"], "remove", reason="Advertising")

    page = (await http.get("/api/admin/log", headers=admin)).json()

    assert page["total"] == 2
    assert [entry["action"] for entry in page["entries"]] == ["removed", "approved"]
    newest = page["entries"][0]
    assert newest["post_id"] == gone["id"]
    assert newest["reason"] == "Advertising"
    assert all(entry["actor_id"] == admin_id for entry in page["entries"])
    assert all(entry["target_user_id"] is None for entry in page["entries"])


async def test_the_trail_narrows_to_what_is_asked_for(
    http: AsyncClient, admin: dict[str, str]
) -> None:
    admin_id = await the_admin_id(http, admin)
    one = await say(http, "First")
    two = await say(http, "Second")
    await decide(http, admin, one["id"], "approve")
    await decide(http, admin, two["id"], "approve")

    just_one = (await http.get(f"/api/admin/log?post_id={one['id']}", headers=admin)).json()
    assert [entry["post_id"] for entry in just_one["entries"]] == [one["id"]]
    assert just_one["total"] == 1

    assert (await http.get("/api/admin/log?actor_id=99999", headers=admin)).json()["total"] == 0
    assert (await http.get(f"/api/admin/log?actor_id={admin_id}", headers=admin)).json()[
        "total"
    ] == 2


async def test_a_second_approval_writes_no_second_line(
    http: AsyncClient, admin: dict[str, str]
) -> None:
    post = await say(http, "Decided once")
    await decide(http, admin, post["id"], "approve")
    await decide(http, admin, post["id"], "approve")  # refused, and it stays refused quietly

    assert (await http.get("/api/admin/log", headers=admin)).json()["total"] == 1


# --- the accounts ---------------------------------------------------------------------


async def test_the_member_list_is_everybody_with_an_account(
    http: AsyncClient, app: FastAPI, admin: dict[str, str]
) -> None:
    await an_account(http, app, "ada_lovelace", "Ada Lovelace")
    await an_account(http, app, "grace_hopper", "Grace Hopper")

    page = (await http.get("/api/admin/members", headers=admin)).json()

    assert page["total"] == 3
    by_name = {member["username"]: member for member in page["members"]}
    assert set(by_name) == {ADMIN["username"], "ada_lovelace", "grace_hopper"}
    assert by_name[ADMIN["username"]]["is_admin"] is True
    assert by_name["ada_lovelace"]["is_admin"] is False
    assert all("password" not in member for member in page["members"])
    assert all(member["deactivated_at"] is None for member in page["members"])


async def test_the_member_list_narrows(
    http: AsyncClient, app: FastAPI, admin: dict[str, str]
) -> None:
    await an_account(http, app, "ada_lovelace", "Ada Lovelace")
    await an_account(http, app, "grace_hopper", "Grace Hopper")

    async def names(query: str) -> list[str]:
        page = (await http.get(f"/api/admin/members?{query}", headers=admin)).json()
        return [member["username"] for member in page["members"]]

    assert await names("search=HOPPER") == ["grace_hopper"]  # the display name, case ignored
    assert await names("search=ada") == ["ada_lovelace"]
    assert await names("search=nobody") == []
    assert await names("admin=true") == [ADMIN["username"]]
    assert await names("deactivated=false") == [
        "grace_hopper",
        "ada_lovelace",
        ADMIN["username"],
    ]  # everybody still on, newest account first


async def test_switching_an_account_off_ends_what_it_had_open(
    http: AsyncClient, app: FastAPI, admin: dict[str, str]
) -> None:
    member = await an_account(http, app, "ada_lovelace", "Ada Lovelace")
    member_id = (await http.get("/api/admin/members?search=ada_lovelace", headers=admin)).json()[
        "members"
    ][0]["id"]

    answer = await http.delete(
        f"/api/admin/members/{member_id}",
        params={"reason": "Harassing other members, repeatedly"},
        headers=admin,
    )

    assert answer.status_code == 200, answer.text
    assert answer.json()["sessions_ended"] == 1
    assert answer.json()["member"]["is_deactivated"] is True

    # Everything they were holding open is shut: the session, the sign in, the password.
    assert (
        await http.get("/api/auth/me", headers=bearer(member["access_token"]))
    ).status_code == 403
    refreshed = await http.post(
        "/api/auth/refresh", json={"refresh_token": member["refresh_token"]}
    )
    assert refreshed.status_code == 401
    assert (
        await http.post(
            "/api/auth/login", json={"username": "ada_lovelace", "password": "hunter2222"}
        )
    ).status_code == 403


async def test_switching_an_account_off_needs_a_reason(
    http: AsyncClient, app: FastAPI, admin: dict[str, str]
) -> None:
    await an_account(http, app, "ada_lovelace", "Ada Lovelace")
    member_id = (await http.get("/api/admin/members?search=ada", headers=admin)).json()["members"][
        0
    ]["id"]

    assert (await http.delete(f"/api/admin/members/{member_id}", headers=admin)).status_code == 400

    # Still on, and still able to sign in.
    assert (
        await http.post(
            "/api/auth/login", json={"username": "ada_lovelace", "password": "hunter2222"}
        )
    ).status_code == 200


async def test_nobody_switches_off_an_admin_or_themselves(
    http: AsyncClient, app: FastAPI, admin: dict[str, str]
) -> None:
    admin_id = await the_admin_id(http, admin)

    # Yourself: the only tool that switches you back on is the one you are holding.
    assert (
        await http.delete(
            f"/api/admin/members/{admin_id}", params={"reason": "Bored"}, headers=admin
        )
    ).status_code == 409

    # Another admin: made one the hard way, because being an admin is decided at a
    # database prompt and not over this API.
    await an_account(http, app, "grace_hopper", "Grace Hopper")
    hopper_id = (await http.get("/api/admin/members?search=grace", headers=admin)).json()[
        "members"
    ][0]["id"]
    async with app.state.container.session_factory() as session:
        await session.execute(update(UserRow).where(UserRow.id == hopper_id).values(is_admin=True))
        await session.commit()

    refused = await http.delete(
        f"/api/admin/members/{hopper_id}", params={"reason": "Try me"}, headers=admin
    )
    assert refused.status_code == 409
    assert "admin" in refused.json()["detail"].lower()


async def test_an_account_switched_off_twice_or_never(
    http: AsyncClient, app: FastAPI, admin: dict[str, str]
) -> None:
    await an_account(http, app, "ada_lovelace", "Ada Lovelace")
    member_id = (await http.get("/api/admin/members?search=ada", headers=admin)).json()["members"][
        0
    ]["id"]
    off = f"/api/admin/members/{member_id}"
    on = f"/api/admin/members/{member_id}/restore"

    assert (await http.post(on, json={}, headers=admin)).status_code == 409
    assert (await http.delete(off, params={"reason": "Spamming"}, headers=admin)).status_code == 200
    assert (await http.delete(off, params={"reason": "Spamming"}, headers=admin)).status_code == 409

    assert (await http.post(on, json={}, headers=admin)).status_code == 200
    assert (await http.post(on, json={}, headers=admin)).status_code == 409
    assert (
        await http.post(
            "/api/auth/login", json={"username": "ada_lovelace", "password": "hunter2222"}
        )
    ).status_code == 200


async def test_one_account_comes_with_its_own_trail(
    http: AsyncClient, app: FastAPI, admin: dict[str, str]
) -> None:
    admin_id = await the_admin_id(http, admin)
    await an_account(http, app, "ada_lovelace", "Ada Lovelace")
    member_id = (await http.get("/api/admin/members?search=ada", headers=admin)).json()["members"][
        0
    ]["id"]
    await http.delete(
        f"/api/admin/members/{member_id}", params={"reason": "Harassment"}, headers=admin
    )

    detail = (await http.get(f"/api/admin/members/{member_id}", headers=admin)).json()

    assert detail["member"]["username"] == "ada_lovelace"
    assert detail["member"]["is_deactivated"] is True
    assert [entry["action"] for entry in detail["history"]] == ["member_deactivated"]
    assert detail["history"][0]["target_user_id"] == member_id
    assert detail["history"][0]["actor_id"] == admin_id
    assert detail["history"][0]["reason"] == "Harassment"

    # The same trail from the other table, filtered to this account.
    filtered = (await http.get(f"/api/admin/log?target_user_id={member_id}", headers=admin)).json()
    assert [entry["action"] for entry in filtered["entries"]] == ["member_deactivated"]
    # and the admin's own account has nothing done to it
    assert (await http.get(f"/api/admin/log?target_user_id={admin_id}", headers=admin)).json()[
        "total"
    ] == 0


async def test_an_account_that_does_not_exist(http: AsyncClient, admin: dict[str, str]) -> None:
    assert (await http.get("/api/admin/members/4242", headers=admin)).status_code == 404
    assert (
        await http.delete("/api/admin/members/4242", params={"reason": "x"}, headers=admin)
    ).status_code == 404


# --- the invites ----------------------------------------------------------------------


async def test_an_invite_is_made_and_sits_there_open(
    http: AsyncClient, admin: dict[str, str]
) -> None:
    answer = await http.post(
        "/api/admin/invites", json={"note": "For Nadia, from the café"}, headers=admin
    )

    assert answer.status_code == 201, answer.text
    invite = answer.json()
    assert invite["state"] == "open"
    assert invite["note"] == "For Nadia, from the café"
    assert invite["used_by_id"] is None
    assert invite["token"]
    # The thing to send is already put together, so nobody copies a token into a URL by hand.
    assert invite["url"] == f"https://{SITE}/join?token={invite['token']}"

    page = (await http.get("/api/admin/invites", headers=admin)).json()
    assert page["total"] == 1
    assert page["invites"][0]["id"] == invite["id"]
    assert page["invites"][0]["url"] == invite["url"]


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("relay.example.org", "https://relay.example.org/join?token=abc"),
        ("https://relay.example.org/", "https://relay.example.org/join?token=abc"),
        ("http://localhost:5173", "http://localhost:5173/join?token=abc"),
        (None, None),
        ("   ", None),
    ],
)
def test_the_link_is_built_from_whatever_was_configured(
    configured: str | None, expected: str | None
) -> None:
    """Whoever sets `INVITE_BASE_URL` copies it out of a browser bar, scheme and all."""
    assert join_invite_link(configured, "abc") == expected


async def test_an_invite_is_spent_by_the_first_person_through_it(
    http: AsyncClient, admin: dict[str, str]
) -> None:
    invite = (await http.post("/api/admin/invites", json={}, headers=admin)).json()

    registered = await http.post(
        "/api/auth/register",
        json={
            "invite_token": invite["token"],
            "username": "ada_lovelace",
            "password": "hunter2222",
            "display_name": "Ada Lovelace",
        },
    )
    assert registered.status_code == 201, registered.text

    seen = (await http.get("/api/admin/invites?state=used", headers=admin)).json()
    assert [entry["id"] for entry in seen["invites"]] == [invite["id"]]
    assert seen["invites"][0]["state"] == "used"
    assert (
        seen["invites"][0]["used_by_id"]
        == (await http.get("/api/admin/members?search=ada", headers=admin)).json()["members"][0][
            "id"
        ]
    )
    assert (await http.get("/api/admin/invites?state=open", headers=admin)).json()["total"] == 0


async def test_an_open_invite_can_be_taken_back(http: AsyncClient, admin: dict[str, str]) -> None:
    invite = (
        await http.post("/api/admin/invites", json={"note": "Wrong person"}, headers=admin)
    ).json()

    answer = await http.delete(f"/api/admin/invites/{invite['id']}", headers=admin)

    assert answer.status_code == 200, answer.text
    assert answer.json()["state"] == "revoked"
    assert (await http.get("/api/admin/invites?state=revoked", headers=admin)).json()["total"] == 1
    # And the door is shut: the token still exists and gets nobody in.
    refused = await http.post(
        "/api/auth/register",
        json={
            "invite_token": invite["token"],
            "username": "ada_lovelace",
            "password": "hunter2222",
            "display_name": "Ada Lovelace",
        },
    )
    assert refused.status_code == 403


async def test_an_invite_that_was_spent_cannot_be_taken_back(
    http: AsyncClient, admin: dict[str, str]
) -> None:
    invite = (await http.post("/api/admin/invites", json={}, headers=admin)).json()

    registered = await http.post(
        "/api/auth/register",
        json={
            "invite_token": invite["token"],
            "username": "ada_lovelace",
            "password": "hunter2222",
            "display_name": "Ada Lovelace",
        },
    )
    assert registered.status_code == 201

    refused = await http.delete(f"/api/admin/invites/{invite['id']}", headers=admin)
    assert refused.status_code == 409
    assert "used" in refused.json()["detail"]


async def test_revoking_the_same_invite_twice(http: AsyncClient, admin: dict[str, str]) -> None:
    invite = (await http.post("/api/admin/invites", json={}, headers=admin)).json()
    path = f"/api/admin/invites/{invite['id']}"

    assert (await http.delete(path, headers=admin)).status_code == 200
    assert (await http.delete(path, headers=admin)).status_code == 409


async def test_an_invite_that_does_not_exist(http: AsyncClient, admin: dict[str, str]) -> None:
    assert (await http.delete("/api/admin/invites/4242", headers=admin)).status_code == 404


async def test_a_note_longer_than_a_note_is_refused(
    http: AsyncClient, admin: dict[str, str]
) -> None:
    assert (
        await http.post("/api/admin/invites", json={"note": "n" * 201}, headers=admin)
    ).status_code == 400
