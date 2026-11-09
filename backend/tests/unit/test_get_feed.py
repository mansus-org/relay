"""The locality feed: only the neighbourhood, newest first, and paged without gaps."""

from datetime import UTC, datetime, timedelta

from relay.contexts.posts.application import GetFeed
from relay.contexts.posts.domain.feed import Cursor
from relay.contexts.posts.domain.post import Post
from tests.fakes.posts import FakePostsUnitOfWork, FixedNeighbourhood, a_post

# The reader is in "here". "next-door" is inside their radius, "elsewhere" is not.
NEIGHBOURHOOD = FixedNeighbourhood({"here": {"here", "next-door"}, "far": {"far"}})
START = datetime(2026, 3, 4, 12, tzinfo=UTC)


def said(*texts: str) -> list[Post]:
    """Posts in the reader's own cell, oldest first, a minute apart."""
    return [
        a_post(text, cell="here", at=START + timedelta(minutes=minute))
        for minute, text in enumerate(texts)
    ]


async def read(uow: FakePostsUnitOfWork, cursor: Cursor | None = None):
    return await GetFeed(uow=uow, neighbourhood=NEIGHBOURHOOD).execute(
        cell="here", radius_km=10, cursor=cursor
    )


async def test_the_newest_post_is_first() -> None:
    uow = FakePostsUnitOfWork(said("older", "newer"))

    page = await read(uow)

    assert [post.body for post in page.posts] == ["newer", "older"]


async def test_a_post_outside_the_radius_is_not_in_this_feed() -> None:
    uow = FakePostsUnitOfWork([*said("here"), a_post("elsewhere", cell="elsewhere")])

    page = await read(uow)

    assert [post.body for post in page.posts] == ["here"]


async def test_a_post_in_a_neighbouring_cell_is_in_this_feed() -> None:
    uow = FakePostsUnitOfWork([a_post("next door", cell="next-door", at=START)])

    page = await read(uow)

    assert [post.body for post in page.posts] == ["next door"]


async def test_a_post_said_without_a_locality_is_in_no_locality_feed() -> None:
    uow = FakePostsUnitOfWork([*said("here"), a_post("nowhere in particular", cell=None)])

    page = await read(uow)

    assert [post.body for post in page.posts] == ["here"]


async def test_a_removed_post_is_in_no_feed() -> None:
    uow = FakePostsUnitOfWork([*said("here"), a_post("taken down", cell="here").removed()])

    page = await read(uow)

    assert [post.body for post in page.posts] == ["here"]


async def test_a_locality_with_nothing_said_in_it_has_an_empty_feed() -> None:
    page = await read(FakePostsUnitOfWork())

    assert page.posts == ()
    assert page.next_cursor is None


async def test_a_page_is_a_page_and_tells_you_where_the_next_one_starts() -> None:
    uow = FakePostsUnitOfWork(said(*[f"post {n}" for n in range(45)]))

    first = await read(uow)

    assert len(first.posts) == GetFeed.PAGE_SIZE
    assert first.posts[0].body == "post 44"
    assert first.next_cursor is not None


async def test_reading_every_page_returns_every_post_once_and_newest_first() -> None:
    uow = FakePostsUnitOfWork(said(*[f"post {n}" for n in range(45)]))
    bodies: list[str] = []
    cursor: Cursor | None = None

    while True:
        page = await read(uow, cursor)
        bodies.extend(post.body for post in page.posts)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor

    assert bodies == [f"post {n}" for n in reversed(range(45))]


async def test_the_last_page_promises_no_more() -> None:
    uow = FakePostsUnitOfWork(said(*[f"post {n}" for n in range(GetFeed.PAGE_SIZE)]))

    page = await read(uow)

    assert len(page.posts) == GetFeed.PAGE_SIZE
    assert page.next_cursor is None


async def test_a_cursor_reads_the_posts_older_than_it_and_not_the_one_it_names() -> None:
    posts = said(*[f"post {n}" for n in range(5)])  # oldest first
    uow = FakePostsUnitOfWork(posts)
    third_newest = posts[2]

    page = await GetFeed(uow=uow, neighbourhood=NEIGHBOURHOOD).execute(
        cell="here", radius_km=10, cursor=Cursor(value=third_newest.created_at)
    )

    assert [post.body for post in page.posts] == ["post 1", "post 0"]
