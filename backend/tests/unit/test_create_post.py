"""Writing a post: it is saved with the time it was said at, and nothing half-said."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from relay.contexts.posts.application import CreatePost
from relay.contexts.posts.domain.cells import UnknownCellError
from relay.shared.domain import ValidationError
from tests.fakes.clock import FixedClock
from tests.fakes.posts import FakePostsUnitOfWork, FixedCells


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
