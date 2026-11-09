"""The feed at the size the ticket set as acceptable: ten thousand posts, sub-100ms."""

import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.contexts.posts.infrastructure.models import PostModel

#: Vigo's resolution-8 cell. The reader is standing in it.
CELL = "883920cd1bfffff"
#: A Coruña's cell, about 170 km away, so the filter has something to throw away.
FAR = "883925cf43fffff"
IN_LOCALITY = 10_000
ELSEWHERE = 1_000


def rows(cell: str, count: int) -> list[dict[str, object]]:
    authors = [uuid4() for _ in range(200)]
    start = datetime(2026, 3, 4, 12, tzinfo=UTC)
    return [
        {
            "id": uuid4(),
            "author_id": authors[index % len(authors)],
            "body": f"Post {index} said in {cell}.",
            "location_cell": cell,
            "created_at": start + timedelta(seconds=index),
            "moderation_status": "pending",
        }
        for index in range(count)
    ]


@pytest.fixture
async def ten_thousand_posts(migrated_engine: AsyncEngine) -> None:
    """Ten thousand said where the reader is, and a thousand said somewhere else."""
    async with migrated_engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                insert(PostModel), rows(CELL, IN_LOCALITY) + rows(FAR, ELSEWHERE)
            )
        )
    async with migrated_engine.connect() as conn:
        stored = await conn.scalar(select(func.count()).select_from(PostModel))
    assert stored == IN_LOCALITY + ELSEWHERE


async def test_the_locality_feed_answers_in_under_a_tenth_of_a_second(
    client: AsyncClient, ten_thousand_posts: None
) -> None:
    started = time.perf_counter()
    response = await client.get("/api/feed", params={"cell": CELL, "radius": 10})
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    body = response.json()
    assert len(body["posts"]) == 20
    assert all(post["location_cell"] == CELL for post in body["posts"])
    assert body["next_cursor"] is not None
    assert elapsed < 0.1, f"the feed took {elapsed * 1000:.0f} ms over 11,000 posts"


async def test_reading_the_next_page_stays_fast(
    client: AsyncClient, ten_thousand_posts: None
) -> None:
    """A page has to walk past everything newer than it, so the last page is the slow one."""
    first = await client.get("/api/feed", params={"cell": CELL, "radius": 10})
    cursor = first.json()["next_cursor"]

    started = time.perf_counter()
    response = await client.get("/api/feed", params={"cell": CELL, "radius": 10, "cursor": cursor})
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert len(response.json()["posts"]) == 20
    assert elapsed < 0.1, f"a paged feed took {elapsed * 1000:.0f} ms over 11,000 posts"
