"""Watching a locality over `/api/stream`: what arrives, what does not, and what is
left behind when the client hangs up.

The stream never ends on its own, and httpx's ASGI transport only hands back a response
once the app has finished writing it. So every test here opens the stream in a task, and
ends it the way a node going away does - `broadcaster.close()` - then reads everything
that came down it.
"""

import asyncio
import json
from collections.abc import AsyncIterator, MutableMapping
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.container import Container
from relay.main import create_app
from relay.shared.config import Settings

#: Vigo and A Coruña, about 170 km apart: far enough that neither locality sees the other.
VIGO = "883920cd1bfffff"
A_CORUNA = "883925cf43fffff"
AUTHOR = UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
async def node(migrated_engine: AsyncEngine, test_settings: Settings) -> AsyncIterator[FastAPI]:
    """An app on a migrated database, keeping a watching client alive every 50ms."""
    app = create_app(test_settings.model_copy(update={"stream_keepalive_seconds": 0.05}))
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
async def client(node: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=node), base_url="http://test") as http:
        yield http


def container(node: FastAPI) -> Container:
    return node.state.container


async def say(http: AsyncClient, body: str, **fields: Any) -> dict:
    response = await http.post("/api/posts", json={"body": body, **fields}, headers=bearer())
    assert response.status_code == 201, response.text
    return response.json()


def bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {AUTHOR}"}


async def watching(http: AsyncClient, cell: str = VIGO, **params: Any) -> asyncio.Task:
    """Open a stream and leave it open, the way a phone watching a locality does."""
    return asyncio.create_task(http.get("/api/stream", params={"cell": cell, **params}))


async def hang_up_and_read(node: FastAPI, stream: asyncio.Task) -> Response:
    """Hang the stream up and hand back everything that came down it."""
    container(node).live_feed.close()
    return await asyncio.wait_for(stream, timeout=5)


async def someone_is_watching(node: FastAPI) -> None:
    """Wait until the stream has actually registered, so a post is never raced."""
    for _ in range(200):
        if container(node).live_feed.readers:
            return
        await asyncio.sleep(0.01)
    pytest.fail(f"the stream never arrived: {len(container(node).live_feed.readers)} readers")


def posts_on(body: str) -> list[dict]:
    """The posts on a stream, read the way the client reads it: `post` events only."""
    return [json.loads(data) for event, data in events(body) if event == "post"]


def comments_on(body: str) -> list[str]:
    return [line for line in body.splitlines() if line.startswith(":")]


def events(body: str) -> list[tuple[str, str]]:
    """Every (event, data) pair on the wire, comments and all, in order."""
    pairs: list[tuple[str, str]] = []
    for block in body.split("\n\n"):
        event, data = "message", ""
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                data = line[len("data: ") :]
        if data:
            pairs.append((event, data))
    return pairs


# What arrives.


async def test_the_stream_is_an_open_stream_of_events(client: AsyncClient, node: FastAPI) -> None:
    stream = await watching(client)
    await someone_is_watching(node)
    response = await hang_up_and_read(node, stream)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"


async def test_a_post_said_in_the_locality_arrives(client: AsyncClient, node: FastAPI) -> None:
    stream = await watching(client)
    await someone_is_watching(node)
    post = await say(client, "Free piano, ground floor.", location_cell=VIGO)

    arrived = posts_on((await hang_up_and_read(node, stream)).text)
    assert [on["id"] for on in arrived] == [post["id"]]


async def test_it_arrives_as_the_same_post_the_feed_would_have_given(
    client: AsyncClient, node: FastAPI
) -> None:
    """One post, two ways of hearing about it: a client has to be able to treat them alike."""
    stream = await watching(client)
    await someone_is_watching(node)
    post = await say(client, "Free piano, ground floor.", location_cell=VIGO)
    arrived = posts_on((await hang_up_and_read(node, stream)).text)[0]

    feed = await client.get("/api/feed", params={"cell": VIGO})
    assert arrived == next(item for item in feed.json()["posts"] if item["id"] == post["id"])


async def test_a_reply_arrives_where_its_thread_was_said(
    client: AsyncClient, node: FastAPI
) -> None:
    """A reply has no cell of its own: it is said where the post it answers was said."""
    post = await say(client, "Anyone else hear the siren?", location_cell=VIGO)
    stream = await watching(client)
    await someone_is_watching(node)
    reply = await say(client, "No, that is the foghorn.", parent_id=post["id"])

    arrived = posts_on((await hang_up_and_read(node, stream)).text)
    assert [on["id"] for on in arrived] == [reply["id"]]


async def test_everything_said_while_watching_arrives_in_order(
    client: AsyncClient, node: FastAPI
) -> None:
    stream = await watching(client)
    await someone_is_watching(node)
    first = await say(client, "First.", location_cell=VIGO)
    second = await say(client, "Second.", location_cell=VIGO)

    arrived = posts_on((await hang_up_and_read(node, stream)).text)
    assert [on["id"] for on in arrived] == [first["id"], second["id"]]
    assert [on["body"] for on in arrived] == ["First.", "Second."]


# What does not.


async def test_a_post_said_in_another_locality_never_arrives(
    client: AsyncClient, node: FastAPI
) -> None:
    stream = await watching(client)
    await someone_is_watching(node)
    await say(client, "Free piano, ground floor.", location_cell=A_CORUNA)

    arrived = posts_on((await hang_up_and_read(node, stream)).text)
    assert arrived == []


async def test_a_post_said_without_a_locality_never_arrives(
    client: AsyncClient, node: FastAPI
) -> None:
    stream = await watching(client)
    await someone_is_watching(node)
    await say(client, "Somewhere, apparently.")

    arrived = posts_on((await hang_up_and_read(node, stream)).text)
    assert arrived == []


async def test_what_was_said_before_you_arrived_is_not_on_the_stream(
    client: AsyncClient, node: FastAPI
) -> None:
    """The backlog is the feed's to give, which is why a reconnect cannot replay."""
    await say(client, "Said before you got here.", location_cell=VIGO)
    stream = await watching(client)
    await someone_is_watching(node)

    arrived = posts_on((await hang_up_and_read(node, stream)).text)
    assert arrived == []


# While nothing is being said.


async def test_a_quiet_locality_says_it_is_still_there(client: AsyncClient, node: FastAPI) -> None:
    stream = await watching(client)
    await asyncio.sleep(0.2)

    arrived = await hang_up_and_read(node, stream)
    assert ": keepalive" in comments_on(arrived.text)


async def test_a_node_going_away_says_goodbye(client: AsyncClient, node: FastAPI) -> None:
    stream = await watching(client)
    await someone_is_watching(node)

    arrived = await hang_up_and_read(node, stream)
    assert ": closed" in comments_on(arrived.text)


# What gets refused, and what gets left behind.


async def test_a_cell_no_feed_reads_is_refused_before_anything_is_streamed(
    client: AsyncClient, node: FastAPI
) -> None:
    response = await client.get("/api/stream", params={"cell": "not-a-cell"})

    assert response.status_code == 400
    assert container(node).live_feed.readers == frozenset()


async def test_a_radius_no_feed_reaches_is_refused(client: AsyncClient, node: FastAPI) -> None:
    response = await client.get("/api/stream", params={"cell": VIGO, "radius": 500})

    assert response.status_code == 400
    assert container(node).live_feed.readers == frozenset()


async def test_a_watcher_who_hung_up_leaves_nothing_behind(node: FastAPI) -> None:
    """The one cleanup no `finally` in the route would have caught.

    httpx cannot hang up mid-stream, so this is the raw ASGI call: the client asks for
    the stream and is gone before a single event is written. The dependency is what
    notices, and the queue has to go with them.
    """
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/api/stream",
        "raw_path": b"/api/stream",
        "query_string": f"cell={VIGO}".encode(),
        "headers": [(b"host", b"test")],
        "scheme": "http",
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
        "root_path": "",
    }

    async def receive() -> MutableMapping[str, Any]:
        return {"type": "http.disconnect"}

    async def send(message: MutableMapping[str, Any]) -> None:
        return None

    await node(scope, receive, send)

    assert container(node).live_feed.readers == frozenset()
