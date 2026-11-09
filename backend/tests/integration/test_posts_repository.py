"""The posts table: what goes in comes back out, and the feed query filters like the domain."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import h3
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.contexts.posts.domain.post import ModerationStatus, Post
from relay.contexts.posts.infrastructure.unit_of_work import SqlAlchemyPostsUnitOfWork
from relay.shared.infrastructure.database import create_session_factory

VIGO = "883920cd1bfffff"
#: A real cell next door to Vigo's, taken from the ring a feed would read.
NEXT_DOOR = next(cell for cell in h3.grid_disk(VIGO, 1) if cell != VIGO)
A_CORUNA = "883925cf43fffff"
START = datetime(2026, 3, 4, 12, tzinfo=UTC)
TOKYO = timezone(timedelta(hours=9))


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


def everything_about(post: Post) -> dict[str, object]:
    """What the row has to get back right.

    A Post is only equal to another Post of the same id, so `got == post` proves the
    row exists and nothing about what is in it.
    """
    return {
        "author_id": post.author_id,
        "body": post.body,
        "created_at": post.created_at,
        "location_cell": post.location_cell,
        "community_id": post.community_id,
        "moderation_status": post.moderation_status,
    }


async def test_a_post_comes_back_as_it_was_said(uow: SqlAlchemyPostsUnitOfWork) -> None:
    """Every field, including the two no endpoint reads back yet."""
    post = said("The bakery on the corner is gone.", community=uuid4())
    taken_down = said("Rude, apparently.", minutes=1).removed()
    await seed(uow, post, taken_down)

    back = await uow.posts.get(post.id)
    assert back is not None
    assert everything_about(back) == everything_about(post)

    taken_down_back = await uow.posts.get(taken_down.id)
    assert taken_down_back is not None
    # The moderation status is stored, not assumed on the way back out.
    assert taken_down_back.moderation_status is ModerationStatus.REMOVED


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


async def test_a_page_starts_at_the_same_instant_when_the_timestamp_comes_in_another_zone(
    uow: SqlAlchemyPostsUnitOfWork,
) -> None:
    """A cursor is an instant, not a wall-clock reading: the same instant pages the same way."""
    posts = [said(f"post {n}", minutes=n) for n in range(5)]
    await seed(uow, *posts)

    in_tokyo = posts[2].created_at.astimezone(TOKYO)
    found = await uow.posts.page_neighbouring(cells=[VIGO], before=in_tokyo, limit=20)

    assert [post.body for post in found] == ["post 1", "post 0"]
