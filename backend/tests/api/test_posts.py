"""The endpoints the mobile screens call: say something, read your locality, look one up,
reply to one, and leave an emoji on it."""

from collections.abc import AsyncIterator
from datetime import datetime
from urllib.parse import quote
from uuid import UUID, uuid4

import h3
import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.contexts.posts.domain.reaction import MAX_EMOJI_LENGTH
from relay.contexts.posts.infrastructure.models import PostModel
from relay.main import create_app
from relay.shared.config import Settings
from tests.fakes.clock import SteppingClock

#: Vigo and A Coruña, about 170 km apart: far enough that neither feed sees the other.
VIGO = "883920cd1bfffff"
A_CORUNA = "883925cf43fffff"
AUTHOR = UUID("11111111-1111-1111-1111-111111111111")
#: A second member, for the tests that need two people in one thread.
READER = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
async def api(test_settings: Settings, migrated_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """A client on a migrated database, on a clock that can tell two posts apart."""
    app = create_app(test_settings)
    async with app.router.lifespan_context(app):
        app.state.container.clock = SteppingClock()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            yield http


def as_(author: UUID = AUTHOR) -> dict[str, str]:
    return {"Authorization": f"Bearer {author}"}


async def say(http: AsyncClient, body: str, **fields: object) -> dict:
    response = await http.post("/api/posts", json={"body": body, **fields}, headers=as_())
    assert response.status_code == 201, response.text
    return response.json()


async def take_down(migrated_engine: AsyncEngine, post_id: str) -> None:
    """Moderation has no endpoint of its own yet, so the row is made to say it was removed."""
    async with migrated_engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                update(PostModel)
                .where(PostModel.id == UUID(post_id))
                .values(moderation_status="removed")
            )
        )


@pytest.fixture
async def taken_down(api: AsyncClient, migrated_engine: AsyncEngine) -> str:
    """A post moderation has since removed."""
    post = await say(api, "Rude, apparently.", location_cell=VIGO)
    await take_down(migrated_engine, post["id"])
    return post["id"]


# Writing.


async def test_saying_something_gives_the_post_back(api: AsyncClient) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)

    assert post["body"] == "The bakery on the corner is gone."
    assert post["author"]["id"] == str(AUTHOR)
    assert post["author"]["name"] == f"Member {str(AUTHOR)[:8]}"
    assert post["location_cell"] == VIGO
    assert UUID(post["id"]) != AUTHOR
    # The compose screen shows "3m ago", so the timestamp has to name its zone.
    assert datetime.fromisoformat(post["created_at"]).tzinfo is not None


async def test_a_post_can_be_said_without_saying_where_it_was_said(api: AsyncClient) -> None:
    assert (await say(api, "Anyone seen a grey cat?"))["location_cell"] is None


async def test_a_post_can_be_said_into_a_community(api: AsyncClient) -> None:
    """A community post names a community instead of a locality, and is accepted."""
    community = uuid4()

    post = await say(api, "Meeting Tuesday?", community_id=str(community))

    assert post["location_cell"] is None


@pytest.mark.parametrize(
    "header", [None, {}, {"Authorization": "Bearer"}, {"Authorization": "Bearer not-a-uuid"}]
)
async def test_writing_needs_someone_to_write_as(api: AsyncClient, header: dict | None) -> None:
    response = await api.post(
        "/api/posts", json={"body": "hello"}, headers=header if header else {}
    )
    assert response.status_code == 401


async def test_a_post_with_nothing_in_it_is_refused(api: AsyncClient) -> None:
    response = await api.post("/api/posts", json={"body": "   "}, headers=as_())

    assert response.status_code == 400
    assert "needs some text" in response.json()["detail"]


async def test_a_post_over_what_the_compose_screen_allows_is_refused(api: AsyncClient) -> None:
    response = await api.post("/api/posts", json={"body": "a" * 501}, headers=as_())

    assert response.status_code == 400
    assert "500" in response.json()["detail"]


async def test_a_post_of_exactly_what_the_compose_screen_allows_is_taken(api: AsyncClient) -> None:
    assert len((await say(api, "a" * 500))["body"]) == 500


async def test_a_post_only_over_the_limit_once_the_spaces_go_is_taken(api: AsyncClient) -> None:
    """What is counted is what was said, not the whitespace a phone leaves around it."""
    post = await say(api, f"  {'a' * 500}  ")

    assert post["body"] == "a" * 500


@pytest.mark.parametrize("said", [{}, {"body": None}, {"body": 4}])
async def test_a_post_with_no_body_at_all_is_refused(api: AsyncClient, said: dict) -> None:
    """No body, a null body, a number for a body: the client is wrong, not the writer."""
    response = await api.post("/api/posts", json=said, headers=as_())

    assert response.status_code == 422


async def test_a_locality_said_as_nothing_at_all_is_no_locality(api: AsyncClient) -> None:
    """An empty cell is the same as not saying where: kept, and in no locality feed."""
    post = await say(api, "Somewhere, maybe.", location_cell="   ")

    assert post["location_cell"] is None
    assert (await api.get("/api/feed", params={"cell": VIGO})).json()["posts"] == []


@pytest.mark.parametrize("cell", ["not-a-cell", "a" * 40])
async def test_a_post_said_in_a_cell_no_feed_reads_is_refused(api: AsyncClient, cell: str) -> None:
    """A post filed where no feed looks is a post its author never sees again."""
    response = await api.post(
        "/api/posts", json={"body": "Somewhere.", "location_cell": cell}, headers=as_()
    )

    assert response.status_code == 400
    assert "H3 cell" in response.json()["detail"]


async def test_a_post_said_in_a_cell_at_the_wrong_resolution_is_refused(api: AsyncClient) -> None:
    """A res-9 cell matches no feed query, so it is refused rather than quietly stored."""
    response = await api.post(
        "/api/posts",
        json={"body": "Somewhere.", "location_cell": h3.cell_to_children(VIGO)[0]},
        headers=as_(),
    )

    assert response.status_code == 400


async def test_a_cell_written_in_uppercase_lands_where_the_feed_reads_it(api: AsyncClient) -> None:
    """One form on the way in, or the post is filed somewhere no read ever asks about."""
    post = await say(api, "Said in the right place.", location_cell=VIGO.upper())

    assert post["location_cell"] == VIGO
    body = (await api.get("/api/feed", params={"cell": VIGO})).json()
    assert [post["body"] for post in body["posts"]] == ["Said in the right place."]


# Reading a locality.


async def test_the_feed_is_public(api: AsyncClient) -> None:
    assert (await api.get("/api/feed", params={"cell": VIGO})).status_code == 200


async def test_the_feed_reads_the_locality_newest_first(api: AsyncClient) -> None:
    await say(api, "older here", location_cell=VIGO)
    await say(api, "newer here", location_cell=VIGO)
    await say(api, "somewhere else entirely", location_cell=A_CORUNA)

    body = (await api.get("/api/feed", params={"cell": VIGO, "radius": 10})).json()

    assert [post["body"] for post in body["posts"]] == ["newer here", "older here"]


async def test_a_post_said_without_a_locality_is_in_no_locality_feed(api: AsyncClient) -> None:
    await say(api, "nowhere in particular")

    body = (await api.get("/api/feed", params={"cell": VIGO})).json()

    assert body["posts"] == []


async def test_a_narrower_radius_reads_fewer_posts(api: AsyncClient) -> None:
    """The radius is the filter, so asking for less of the map has to change the answer."""
    lat, lng = h3.cell_to_latlng(VIGO)
    a_few_km_out = h3.latlng_to_cell(lat + 0.05, lng, 8)
    await say(api, "next door", location_cell=VIGO)
    await say(api, "a few km out", location_cell=a_few_km_out)

    wide = (await api.get("/api/feed", params={"cell": VIGO, "radius": 10})).json()
    narrow = (await api.get("/api/feed", params={"cell": VIGO, "radius": 1})).json()

    assert [post["body"] for post in wide["posts"]] == ["a few km out", "next door"]
    assert [post["body"] for post in narrow["posts"]] == ["next door"]


async def test_the_feed_pages_and_tells_you_where_the_next_page_starts(api: AsyncClient) -> None:
    for index in range(25):
        await say(api, f"post {index}", location_cell=VIGO)

    first = (await api.get("/api/feed", params={"cell": VIGO})).json()
    assert len(first["posts"]) == 20
    assert first["next_cursor"] is not None
    # A `+` in a query string arrives as a space, which is no longer a timestamp.
    assert "+" not in first["next_cursor"]

    second = (
        await api.get("/api/feed", params={"cell": VIGO, "cursor": first["next_cursor"]})
    ).json()

    assert [post["body"] for post in second["posts"]] == [f"post {n}" for n in range(4, -1, -1)]
    assert second["next_cursor"] is None
    seen = [post["id"] for post in first["posts"] + second["posts"]]
    assert len(set(seen)) == 25


async def test_the_feed_needs_a_cell(api: AsyncClient) -> None:
    assert (await api.get("/api/feed")).status_code == 422


@pytest.mark.parametrize("cell", ["", "not-a-cell"])
async def test_the_feed_refuses_a_cell_it_cannot_read(api: AsyncClient, cell: str) -> None:
    response = await api.get("/api/feed", params={"cell": cell})

    assert response.status_code == 400
    assert "H3 cell" in response.json()["detail"]


async def test_a_cell_at_the_wrong_resolution_is_refused(api: AsyncClient) -> None:
    """A res-7 cell would match no post at all, so it is refused rather than answered empty."""
    response = await api.get("/api/feed", params={"cell": h3.latlng_to_cell(42.23, -8.72, 7)})

    assert response.status_code == 400


@pytest.mark.parametrize("radius", [0, -1, 25.1, 26, float("nan"), float("inf")])
async def test_the_feed_refuses_a_radius_that_would_read_too_far(
    api: AsyncClient, radius: float
) -> None:
    """Including the two radii that are not distances at all: a radius that reads the
    whole planet, or no distance, is the client's mistake to hear about."""
    assert (await api.get("/api/feed", params={"cell": VIGO, "radius": radius})).status_code == 400


async def test_the_widest_radius_the_feed_will_read_is_read(api: AsyncClient) -> None:
    """25 km is the ceiling and it is inclusive, so it is answered, not refused."""
    await say(api, "Down the road.", location_cell=VIGO)

    response = await api.get("/api/feed", params={"cell": VIGO, "radius": 25})

    assert response.status_code == 200
    assert [post["body"] for post in response.json()["posts"]] == ["Down the road."]


async def test_a_cursor_this_feed_never_handed_out_is_refused(api: AsyncClient) -> None:
    response = await api.get("/api/feed", params={"cell": VIGO, "cursor": "yesterday"})

    assert response.status_code == 400


async def test_an_empty_cursor_is_not_a_page(api: AsyncClient) -> None:
    """A client that clears its cursor may still send the parameter, and that is not a time."""
    assert (await api.get("/api/feed", params={"cell": VIGO, "cursor": ""})).status_code == 400


async def test_a_post_taken_down_is_out_of_the_feed(api: AsyncClient, taken_down: str) -> None:
    assert (await api.get("/api/feed", params={"cell": VIGO})).json()["posts"] == []


async def test_a_post_taken_down_reports_itself_gone(api: AsyncClient, taken_down: str) -> None:
    assert (await api.get(f"/api/posts/{taken_down}")).status_code == 404


# Reading one post.


async def test_a_post_can_be_read_on_its_own(api: AsyncClient) -> None:
    created = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)

    response = await api.get(f"/api/posts/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


async def test_a_post_that_was_never_said_is_not_there(api: AsyncClient) -> None:
    assert (await api.get(f"/api/posts/{uuid4()}")).status_code == 404


async def test_every_endpoint_is_in_the_openapi_document(api: AsyncClient) -> None:
    paths = (await api.get("/openapi.json")).json()["paths"]

    assert {
        "/api/posts",
        "/api/feed",
        "/api/posts/{post_id}",
        "/api/posts/{post_id}/replies",
        "/api/posts/{post_id}/reactions",
        "/api/posts/{post_id}/reactions/{emoji}",
    } <= set(paths)


# The shapes the mobile client already reads, field for field.


async def test_the_post_shape_is_the_one_the_mobile_client_parses(api: AsyncClient) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)

    assert set(post) >= {"id", "author", "body", "created_at", "parent_id"}
    assert set(post["author"]) == {"id", "name"}
    # The client tolerates these being absent; the backend sends them anyway.
    assert post["reactions"] == []
    assert post["reply_count"] == 0
    # A post of its own answers nothing.
    assert post["parent_id"] is None


# Replying.


async def reply_to(
    http: AsyncClient, post_id: str, body: str, *, who: UUID = AUTHOR, **fields: object
) -> dict:
    """Say something under a post, and hand back the post that was made."""
    response = await http.post(
        "/api/posts", json={"body": body, "parent_id": post_id, **fields}, headers=as_(who)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def thread_of(http: AsyncClient, post_id: str) -> list[dict]:
    """The replies under a post, oldest first."""
    response = await http.get(f"/api/posts/{post_id}/replies")
    assert response.status_code == 200, response.text
    return response.json()["posts"]


async def test_a_reply_lands_under_the_post_it_answers(api: AsyncClient) -> None:
    root = await say(api, "Is the bakery closing for good?", location_cell=VIGO)

    reply = await reply_to(api, root["id"], "They are on holiday, back Monday.")

    assert reply["parent_id"] == root["id"]
    assert [post["body"] for post in await thread_of(api, root["id"])] == [
        "They are on holiday, back Monday."
    ]


async def test_a_reply_is_said_where_the_post_it_answers_was(api: AsyncClient) -> None:
    """Nobody says where they are twice: a reply lands in its parent's locality."""
    root = await say(api, "Is the bakery closing for good?", location_cell=VIGO)

    reply = await reply_to(api, root["id"], "Back Monday.")

    assert reply["location_cell"] == VIGO


async def test_a_reply_said_elsewhere_is_still_under_its_own_post(api: AsyncClient) -> None:
    """Answering from another town does not move the answer to that town's thread."""
    root = await say(api, "Is the bakery closing for good?", location_cell=VIGO)

    reply = await reply_to(api, root["id"], "Reading this from A Coruna.", location_cell=A_CORUNA)

    assert reply["location_cell"] == A_CORUNA
    assert [post["body"] for post in await thread_of(api, root["id"])] == [
        "Reading this from A Coruna."
    ]


async def test_a_reply_cannot_move_a_thread_into_another_community(api: AsyncClient) -> None:
    root = await say(api, "Meeting Tuesday?", community_id=str(uuid4()))

    response = await api.post(
        "/api/posts",
        json={"body": "Over here instead.", "parent_id": root["id"], "community_id": str(uuid4())},
        headers=as_(),
    )

    assert response.status_code == 400
    assert await thread_of(api, root["id"]) == []


async def test_the_replies_under_a_post_are_oldest_first(api: AsyncClient) -> None:
    root = await say(api, "Is the bakery closing for good?", location_cell=VIGO)
    await reply_to(api, root["id"], "Mine closed in January.")
    await reply_to(api, root["id"], "Back Monday.")

    replies = await thread_of(api, root["id"])

    assert [post["body"] for post in replies] == ["Mine closed in January.", "Back Monday."]
    assert [post["parent_id"] for post in replies] == [root["id"], root["id"]]


async def test_a_reply_to_a_reply_is_under_the_reply(api: AsyncClient) -> None:
    """A thread opens one level per call; nothing pretends to be flatter than it is."""
    root = await say(api, "Is the bakery closing for good?", location_cell=VIGO)
    answer = await reply_to(api, root["id"], "They are on holiday, back Monday.")
    await reply_to(api, answer["id"], "Thanks for telling me.")

    assert [post["body"] for post in await thread_of(api, root["id"])] == [
        "They are on holiday, back Monday."
    ]
    assert [post["body"] for post in await thread_of(api, answer["id"])] == [
        "Thanks for telling me."
    ]


async def test_a_reply_counts_itself_in_the_post_it_answers(api: AsyncClient) -> None:
    root = await say(api, "Is the bakery closing for good?", location_cell=VIGO)
    assert (await api.get(f"/api/posts/{root['id']}")).json()["reply_count"] == 0

    await reply_to(api, root["id"], "Back Monday.")

    assert (await api.get(f"/api/posts/{root['id']}")).json()["reply_count"] == 1


async def test_a_reply_carries_its_own_replies_and_reactions(api: AsyncClient) -> None:
    root = await say(api, "Is the bakery closing for good?", location_cell=VIGO)
    answer = await reply_to(api, root["id"], "They are on holiday, back Monday.")
    await reply_to(api, answer["id"], "Thanks for telling me.")
    await react(api, answer["id"], "❤️", who=READER)

    reply = (await thread_of(api, root["id"]))[0]

    assert reply["id"] == answer["id"]
    assert reply["reply_count"] == 1
    assert reply["reactions"] == [{"emoji": "❤️", "count": 1, "mine": False}]


async def test_the_locality_feed_is_a_feed_of_posts_not_of_answers(api: AsyncClient) -> None:
    """An answer is read under the post it answers, not as a card of its own."""
    root = await say(api, "Is the bakery closing for good?", location_cell=VIGO)
    await reply_to(api, root["id"], "Back Monday.")

    posts = await api.get("/api/feed", params={"cell": VIGO})
    assert [post["id"] for post in posts.json()["posts"]] == [root["id"]]


async def test_a_reply_to_a_post_that_was_never_said_is_refused(api: AsyncClient) -> None:
    response = await api.post(
        "/api/posts",
        json={"body": "Back Monday.", "parent_id": str(uuid4())},
        headers=as_(),
    )

    assert response.status_code == 404


async def test_a_reply_to_a_post_taken_down_is_refused(api: AsyncClient, taken_down: str) -> None:
    response = await api.post(
        "/api/posts",
        json={"body": "+1", "parent_id": taken_down},
        headers=as_(),
    )

    assert response.status_code == 404


async def test_a_taken_down_reply_is_out_of_its_thread(
    api: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    root = await say(api, "Is the bakery closing for good?", location_cell=VIGO)
    rude = await reply_to(api, root["id"], "Something rude.")
    await reply_to(api, root["id"], "Back Monday.")
    await take_down(migrated_engine, rude["id"])

    assert [post["body"] for post in await thread_of(api, root["id"])] == ["Back Monday."]
    assert (await api.get(f"/api/posts/{rude['id']}")).status_code == 404


async def test_reading_a_thread_needs_no_one_to_be_signed_in(api: AsyncClient) -> None:
    root = await say(api, "Is the bakery closing for good?", location_cell=VIGO)
    await reply_to(api, root["id"], "Back Monday.")

    response = await api.get(f"/api/posts/{root['id']}/replies")

    assert response.status_code == 200
    assert [post["body"] for post in response.json()["posts"]] == ["Back Monday."]


async def test_a_post_that_was_never_said_has_no_thread(api: AsyncClient) -> None:
    assert (await api.get(f"/api/posts/{uuid4()}/replies")).status_code == 404


# Reacting.


async def react(http: AsyncClient, post_id: str, emoji: str, *, who: UUID = AUTHOR) -> Response:
    return await http.post(
        f"/api/posts/{post_id}/reactions", json={"emoji": emoji}, headers=as_(who)
    )


async def take_back(http: AsyncClient, post_id: str, emoji: str, *, who: UUID = AUTHOR) -> Response:
    """The emoji goes in the path, so it has to be escaped on the way there."""
    return await http.delete(f"/api/posts/{post_id}/reactions/{quote(emoji)}", headers=as_(who))


async def shown_reactions(http: AsyncClient, post_id: str, *, who: UUID | None = None) -> list:
    headers = as_(who) if who is not None else {}
    return (await http.get(f"/api/posts/{post_id}", headers=headers)).json()["reactions"]


async def test_an_emoji_goes_on_a_post_and_comes_back_counted(api: AsyncClient) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)

    response = await react(api, post["id"], "❤️")

    assert response.status_code == 201
    assert response.json() == {"emoji": "❤️", "count": 1, "mine": True}
    assert await shown_reactions(api, post["id"]) == [{"emoji": "❤️", "count": 1, "mine": False}]


async def test_the_same_emoji_twice_from_one_person_counts_once(api: AsyncClient) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)
    await react(api, post["id"], "❤️")

    response = await react(api, post["id"], "❤️")

    assert response.status_code == 409
    assert await shown_reactions(api, post["id"], who=AUTHOR) == [
        {"emoji": "❤️", "count": 1, "mine": True}
    ]


async def test_two_people_who_feel_the_same_make_it_two(api: AsyncClient) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)
    await react(api, post["id"], "❤️", who=AUTHOR)

    response = await react(api, post["id"], "❤️", who=READER)

    assert response.json() == {"emoji": "❤️", "count": 2, "mine": True}


async def test_a_second_emoji_is_a_different_thing_said(api: AsyncClient) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)
    await react(api, post["id"], "❤️")

    response = await react(api, post["id"], "🎉")

    assert response.status_code == 201
    assert await shown_reactions(api, post["id"], who=AUTHOR) == [
        {"emoji": "❤️", "count": 1, "mine": True},
        {"emoji": "🎉", "count": 1, "mine": True},
    ]


async def test_the_emojis_under_a_post_are_ordered_most_used_first(api: AsyncClient) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)
    await react(api, post["id"], "🎉", who=READER)
    for person in (AUTHOR, READER, uuid4()):
        await react(api, post["id"], "❤️", who=person)

    assert [emoji["emoji"] for emoji in await shown_reactions(api, post["id"])] == ["❤️", "🎉"]


async def test_taking_an_emoji_back_takes_it_off(api: AsyncClient) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)
    await react(api, post["id"], "❤️")
    await react(api, post["id"], "❤️", who=READER)

    response = await take_back(api, post["id"], "❤️")

    assert response.status_code == 204
    assert await shown_reactions(api, post["id"], who=READER) == [
        {"emoji": "❤️", "count": 1, "mine": True}
    ]


async def test_taking_back_an_emoji_you_never_left_is_reported(api: AsyncClient) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)
    await react(api, post["id"], "❤️", who=READER)

    assert (await take_back(api, post["id"], "❤️")).status_code == 404


async def test_someone_elses_emoji_is_not_theirs_to_take(api: AsyncClient) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)
    await react(api, post["id"], "❤️", who=READER)

    assert (await take_back(api, post["id"], "❤️", who=AUTHOR)).status_code == 404
    assert await shown_reactions(api, post["id"], who=READER) == [
        {"emoji": "❤️", "count": 1, "mine": True}
    ]


async def test_reacting_needs_someone_to_react_as(api: AsyncClient) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)

    response = await api.post(f"/api/posts/{post['id']}/reactions", json={"emoji": "❤️"})

    assert response.status_code == 401


async def test_reacting_needs_a_post_that_is_still_up(api: AsyncClient, taken_down: str) -> None:
    assert (await react(api, taken_down, "❤️")).status_code == 404
    assert (await react(api, str(uuid4()), "❤️")).status_code == 404


@pytest.mark.parametrize("emoji", ["", "   ", "i love it", "a" * (MAX_EMOJI_LENGTH + 1)])
async def test_an_emoji_has_to_be_an_emoji(api: AsyncClient, emoji: str) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)

    response = await react(api, post["id"], emoji)

    assert response.status_code == 400


async def test_the_emoji_has_to_be_said_at_all(api: AsyncClient) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)

    response = await api.post(f"/api/posts/{post['id']}/reactions", json={}, headers=as_(AUTHOR))

    assert response.status_code == 422


async def test_the_reader_sees_their_own_emoji_marked(api: AsyncClient) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)
    await react(api, post["id"], "👍", who=READER)

    assert await shown_reactions(api, post["id"], who=READER) == [
        {"emoji": "👍", "count": 1, "mine": True}
    ]
    assert await shown_reactions(api, post["id"], who=uuid4()) == [
        {"emoji": "👍", "count": 1, "mine": False}
    ]


async def test_the_reactions_show_up_in_the_feed(api: AsyncClient) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)
    await react(api, post["id"], "👍", who=READER)

    shown = (await api.get("/api/feed", params={"cell": VIGO})).json()["posts"][0]

    assert shown["id"] == post["id"]
    assert shown["reactions"] == [{"emoji": "👍", "count": 1, "mine": False}]
    assert shown["reply_count"] == 0
