"""Writing a post: it is saved with the time it was said at, and nothing half-said."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from relay.contexts.posts.application import CreatePost
from relay.contexts.posts.domain.cells import UnknownCellError
from relay.contexts.posts.domain.post import PostNotFoundError
from relay.shared.domain import ValidationError
from tests.fakes.clock import FixedClock
from tests.fakes.posts import FakePostsUnitOfWork, FixedCells, a_post


async def test_a_post_is_saved_and_handed_back_with_the_time_it_was_said() -> None:
    uow = FakePostsUnitOfWork()
    author = uuid4()
    use_case = CreatePost(
        uow=uow,
        clock=FixedClock(datetime(2026, 3, 4, 9, 30, tzinfo=UTC)),
        cells=FixedCells(),
    )

    post = await use_case.execute(
        author_id=author, body="The bakery on the corner is gone.", location_cell="here"
    )

    assert uow.committed is True
    assert await uow.posts.get(post.id) is not None
    assert post.author_id == author
    assert post.created_at == datetime(2026, 3, 4, 9, 30, tzinfo=UTC)
    assert post.location_cell == "here"


async def test_a_post_can_be_said_without_a_locality_or_a_community() -> None:
    uow = FakePostsUnitOfWork()
    use_case = CreatePost(uow=uow, clock=FixedClock(), cells=FixedCells())

    post = await use_case.execute(author_id=uuid4(), body="Anyone seen a grey cat?")

    assert post.location_cell is None
    assert post.community_id is None
    assert uow.committed is True


async def test_a_locality_left_blank_is_no_locality_rather_than_a_cell_of_its_own() -> None:
    uow = FakePostsUnitOfWork()
    use_case = CreatePost(uow=uow, clock=FixedClock(), cells=FixedCells())

    post = await use_case.execute(author_id=uuid4(), body="Anyone?", location_cell="   ")

    assert post.location_cell is None


async def test_a_post_said_in_a_cell_no_feed_reads_is_not_saved() -> None:
    """A post filed where no feed looks is a post its author never sees again."""
    uow = FakePostsUnitOfWork()
    use_case = CreatePost(uow=uow, clock=FixedClock(), cells=FixedCells())

    with pytest.raises(UnknownCellError):
        await use_case.execute(
            author_id=uuid4(), body="Somewhere that is not a cell.", location_cell="99"
        )

    assert uow.committed is False
    assert await uow.posts.page_neighbouring(cells=["here"], before=None, limit=20) == []


async def test_nothing_is_committed_when_a_post_was_never_said() -> None:
    uow = FakePostsUnitOfWork()
    use_case = CreatePost(uow=uow, clock=FixedClock(), cells=FixedCells())

    with pytest.raises(ValidationError, match="needs some text"):
        await use_case.execute(author_id=uuid4(), body="   ")

    assert uow.committed is False
    assert await uow.posts.page_neighbouring(cells=["here"], before=None, limit=20) == []


async def test_a_reply_keeps_the_post_it_answers() -> None:
    root = a_post("Is the bakery closing for good?")
    uow = FakePostsUnitOfWork([root])
    use_case = CreatePost(uow=uow, clock=FixedClock(), cells=FixedCells())

    reply = await use_case.execute(author_id=uuid4(), body="Back Monday.", parent_id=root.id)

    assert reply.parent_id == root.id
    assert uow.committed is True
    assert [post.body for post in await uow.posts.replies_to(root.id)] == ["Back Monday."]


async def test_a_reply_is_said_where_the_post_it_answers_was() -> None:
    """Nobody has to say where they are twice: a reply lands in its parent's locality."""
    community = uuid4()
    root = a_post("Is the bakery closing for good?", community_id=community)
    uow = FakePostsUnitOfWork([root])
    use_case = CreatePost(uow=uow, clock=FixedClock(), cells=FixedCells())

    reply = await use_case.execute(author_id=uuid4(), body="Back Monday.", parent_id=root.id)

    assert reply.location_cell == "here"
    assert reply.community_id == community


async def test_a_reply_into_another_community_is_refused() -> None:
    """A thread lives in one community; an answer cannot be filed into another."""
    root = a_post("Is the bakery closing for good?", community_id=uuid4())
    uow = FakePostsUnitOfWork([root])
    use_case = CreatePost(uow=uow, clock=FixedClock(), cells=FixedCells())

    with pytest.raises(ValidationError, match="community its parent is in"):
        await use_case.execute(
            author_id=uuid4(),
            body="Over here instead.",
            parent_id=root.id,
            community_id=uuid4(),
        )

    assert uow.committed is False
    assert await uow.posts.replies_to(root.id) == []


async def test_a_reply_to_a_post_that_was_never_said_is_refused() -> None:
    """An answer to nothing is filed where no thread will ever show it, so it is not filed."""
    uow = FakePostsUnitOfWork()
    use_case = CreatePost(uow=uow, clock=FixedClock(), cells=FixedCells())
    nowhere = uuid4()

    with pytest.raises(PostNotFoundError):
        await use_case.execute(author_id=uuid4(), body="Back Monday.", parent_id=nowhere)

    assert uow.committed is False
    assert await uow.posts.replies_to(nowhere) == []


async def test_a_reply_to_a_post_taken_down_is_refused() -> None:
    taken_down = a_post("Rude, apparently.").removed()
    uow = FakePostsUnitOfWork([taken_down])
    use_case = CreatePost(uow=uow, clock=FixedClock(), cells=FixedCells())

    with pytest.raises(PostNotFoundError):
        await use_case.execute(author_id=uuid4(), body="+1", parent_id=taken_down.id)

    assert uow.committed is False
