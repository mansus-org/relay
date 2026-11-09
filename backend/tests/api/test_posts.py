"""The three endpoints the mobile screens call: say something, read your locality, look one up."""

from collections.abc import AsyncIterator
from datetime import datetime
from uuid import UUID, uuid4

import h3
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.contexts.posts.infrastructure.models import PostModel
from relay.main import create_app
from relay.shared.config import Settings
from tests.fakes.clock import SteppingClock

#: Vigo and A Coruña, about 170 km apart: far enough that neither feed sees the other.
VIGO = "883920cd1bfffff"
A_CORUNA = "883925cf43fffff"
AUTHOR = UUID("11111111-1111-1111-1111-111111111111")


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


@pytest.fixture
async def taken_down(api: AsyncClient, migrated_engine: AsyncEngine) -> str:
    """A post moderation has since removed. No endpoint can do that yet, so the row does."""
    post = await say(api, "Rude, apparently.", location_cell=VIGO)
    async with migrated_engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                update(PostModel)
                .where(PostModel.id == UUID(post["id"]))
                .values(moderation_status="removed")
            )
        )
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

    assert {"/api/posts", "/api/feed", "/api/posts/{post_id}"} <= set(paths)


# The shapes the mobile client already reads, field for field.


async def test_the_post_shape_is_the_one_the_mobile_client_parses(api: AsyncClient) -> None:
    post = await say(api, "The bakery on the corner is gone.", location_cell=VIGO)

    assert set(post) >= {"id", "author", "body", "created_at"}
    assert set(post["author"]) == {"id", "name"}
    # The client tolerates these being absent; the backend sends them anyway.
    assert post["reactions"] == []
    assert post["reply_count"] == 0
