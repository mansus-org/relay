"""A thread at the size a popular post reaches: ten thousand answers, read in one call.

The same argument as the feed's. The answer has to be the whole thread, in the order it
happened; and the read has to stay quick, which the index either supports or does not.
The count matters as much as the plan here: a reply carries its parent's locality, so a
thread is read through `parent_id` and nothing else, and a tally is asked for every reply
in it.
"""

import time
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.contexts.posts.infrastructure.models import PostModel
from relay.contexts.posts.infrastructure.repository import replies_statement

REPLIES = 10_000
#: Loose for the same reason the feed's ceiling is: the plan says more than a stopwatch
#: on a shared runner does.
CEILING_S = 1.0
AUTHORS = [uuid4() for _ in range(50)]
START = datetime(2026, 4, 1, 9, tzinfo=UTC)


def reply_rows(parent: UUID, count: int) -> list[dict[str, object]]:
    return [
        {
            "id": uuid4(),
            "author_id": AUTHORS[index % len(AUTHORS)],
            "body": f"Answer {index}.",
            "parent_id": parent,
            "location_cell": "883920cd1bfffff",
            "created_at": START + timedelta(seconds=index),
            "moderation_status": "pending",
        }
        for index in range(count)
    ]


@pytest.fixture
async def a_post_with_ten_thousand_answers(migrated_engine: AsyncEngine) -> UUID:
    """One post, and everything said under it, plus a thousand said under another."""
    root = uuid4()
    other = uuid4()
    payload: list[dict[str, object]] = [
        {
            "id": id_,
            "author_id": AUTHORS[0],
            "body": "Is the bakery closing for good?",
            "parent_id": None,
            "created_at": START,
            "moderation_status": "pending",
        }
        for id_ in (root, other)
    ]
    payload += reply_rows(root, REPLIES) + reply_rows(other, 1_000)
    async with migrated_engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: sync_conn.execute(insert(PostModel), payload))
    async with migrated_engine.connect() as conn:
        if migrated_engine.dialect.name == "postgresql":
            await conn.exec_driver_sql("ANALYZE posts")
        stored = await conn.scalar(select(func.count()).select_from(PostModel))
    assert stored == len(payload)
    return root


async def test_the_answers_come_back_in_the_order_they_were_said(
    client: AsyncClient, a_post_with_ten_thousand_answers: UUID
) -> None:
    response = await client.get(f"/api/posts/{a_post_with_ten_thousand_answers}/replies")

    body = response.json()
    assert response.status_code == 200
    assert len(body["posts"]) == REPLIES
    assert [reply["body"] for reply in body["posts"][:3]] == [
        "Answer 0.",
        "Answer 1.",
        "Answer 2.",
    ]


async def test_reading_a_whole_thread_answers_in_under_a_second(
    client: AsyncClient, a_post_with_ten_thousand_answers: UUID
) -> None:
    started = time.perf_counter()
    response = await client.get(f"/api/posts/{a_post_with_ten_thousand_answers}/replies")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    print(f"\nthread of {REPLIES} answers: {elapsed * 1000:.1f} ms")
    assert elapsed < CEILING_S, f"opening the thread took {elapsed * 1000:.0f} ms"


async def test_the_thread_query_walks_the_index_it_was_given(
    migrated_engine: AsyncEngine, a_post_with_ten_thousand_answers: UUID
) -> None:
    """Opening a thread is one parent and its replies forwards in time: that is the index."""
    sql = str(
        replies_statement(a_post_with_ten_thousand_answers).compile(
            dialect=migrated_engine.sync_engine.dialect, compile_kwargs={"literal_binds": True}
        )
    )
    explain = (
        "EXPLAIN (ANALYZE, FORMAT JSON)"
        if migrated_engine.dialect.name == "postgresql"
        else "EXPLAIN QUERY PLAN"
    )
    async with migrated_engine.connect() as conn:
        found = (await conn.exec_driver_sql(f"{explain} {sql}")).all()
    plan = "\n".join(" ".join(str(cell) for cell in row) for row in found)

    assert "ix_posts_parent_id_created_at" in plan, plan
