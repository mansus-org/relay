"""The posts table: what goes in comes back out, and the feed query filters like the domain."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.contexts.posts.domain.post import Post
from relay.contexts.posts.infrastructure.repository import feed_statement
from relay.contexts.posts.infrastructure.unit_of_work import SqlAlchemyPostsUnitOfWork
from relay.shared.infrastructure.database import create_session_factory

VIGO = "883920cd1bfffff"
NEXT_DOOR = "883920cd1bffffe"
A_CORUNA = "883925cf43fffff"
START = datetime(2026, 3, 4, 12, tzinfo=UTC)


@pytest.fixture
async def uow(migrated_engine: AsyncEngine) -> AsyncIterator[SqlAlchemyPostsUnitOfWork]:
    unit = SqlAlchemyPostsUnitOfWork(create_session_factory(migrated_engine))
    async with unit:
        yield unit


def said(
    text: str,
    *,
    cell: str | None = VIGO,
    minutes: int = 0,
    community: UUID | None = None,
) -> Post:
    return Post.write(
        author_id=uuid4(),
        body=text,
        created_at=START + timedelta(minutes=minutes),
        location_cell=cell,
        community_id=community,
    )


async def seed(uow: SqlAlchemyPostsUnitOfWork, *posts: Post) -> None:
    for post in posts:
        await uow.posts.add(post)
    await uow.commit()


async def test_a_post_comes_back_as_it_was_said(uow: SqlAlchemyPostsUnitOfWork) -> None:
    """Every field, including the two no endpoint reads back yet."""
    post = said("The bakery on the corner is gone.", community=uuid4())
    taken_down = said("Rude, apparently.", minutes=1).removed()
    await seed(uow, post, taken_down)

    assert await uow.posts.get(post.id) == post
    # The moderation status is stored, not assumed on the way back out.
    assert await uow.posts.get(taken_down.id) == taken_down


async def test_a_post_that_was_never_said_comes_back_as_nothing(
    uow: SqlAlchemyPostsUnitOfWork,
) -> None:
    assert await uow.posts.get(uuid4()) is None


async def test_the_feed_reads_the_cells_it_is_given_and_no_others(
    uow: SqlAlchemyPostsUnitOfWork,
) -> None:
    await seed(
        uow,
        said("here", minutes=1),
        said("next door", cell=NEXT_DOOR, minutes=2),
        said("on the other side of the region", cell=A_CORUNA, minutes=3),
    )

    found = await uow.posts.page_neighbouring(cells=[VIGO, NEXT_DOOR], before=None, limit=20)

    assert [post.body for post in found] == ["next door", "here"]


async def test_a_post_said_without_a_locality_is_in_no_feed(
    uow: SqlAlchemyPostsUnitOfWork,
) -> None:
    await seed(uow, said("here"), said("nowhere in particular", cell=None))

    found = await uow.posts.page_neighbouring(cells=[VIGO], before=None, limit=20)

    assert [post.body for post in found] == ["here"]


async def test_a_removed_post_is_in_no_feed(uow: SqlAlchemyPostsUnitOfWork) -> None:
    await seed(uow, said("here", minutes=1), said("taken down", minutes=2).removed())

    found = await uow.posts.page_neighbouring(cells=[VIGO], before=None, limit=20)

    assert [post.body for post in found] == ["here"]


async def test_the_newest_post_comes_first_and_a_page_stops_where_it_should(
    uow: SqlAlchemyPostsUnitOfWork,
) -> None:
    await seed(uow, *[said(f"post {n}", minutes=n) for n in range(5)])

    found = await uow.posts.page_neighbouring(cells=[VIGO], before=None, limit=2)

    assert [post.body for post in found] == ["post 4", "post 3"]


async def test_a_page_starts_after_the_timestamp_it_is_given(
    uow: SqlAlchemyPostsUnitOfWork,
) -> None:
    posts = [said(f"post {n}", minutes=n) for n in range(5)]
    await seed(uow, *posts)

    found = await uow.posts.page_neighbouring(cells=[VIGO], before=posts[2].created_at, limit=20)

    assert [post.body for post in found] == ["post 1", "post 0"]


async def test_the_feed_query_walks_the_index_it_was_given(
    migrated_engine: AsyncEngine,
) -> None:
    """An index the query never uses is decoration, so the plan is part of the contract."""
    if migrated_engine.dialect.name != "sqlite":
        pytest.skip("the plan is read SQLite's way here")

    query = feed_statement([VIGO, NEXT_DOOR], before=None, limit=21).compile(
        dialect=migrated_engine.sync_engine.dialect, compile_kwargs={"literal_binds": True}
    )
    async with migrated_engine.connect() as conn:
        plan = (await conn.exec_driver_sql(f"EXPLAIN QUERY PLAN {query}")).all()

    assert any("ix_posts_location_cell_created_at" in str(row) for row in plan), plan
