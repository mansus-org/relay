"""In-memory stand-ins for the posts ports, so a use-case test never touches a database."""

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from relay.contexts.posts.application.unit_of_work import PostsUnitOfWork
from relay.contexts.posts.domain.cells import UnknownCellError
from relay.contexts.posts.domain.ports import CellNeighbourhood, CellStandard, PostRepository
from relay.contexts.posts.domain.post import Post
from tests.fakes.repository import InMemoryRepository
from tests.fakes.unit_of_work import FakeUnitOfWork


def a_post(
    text: str = "A bar in my street closed.",
    *,
    cell: str | None = "here",
    at: datetime = datetime(2026, 1, 1, 12, tzinfo=UTC),
    author_id: UUID | None = None,
) -> Post:
    """A post a test can name in one line."""
    return Post.write(author_id=author_id or uuid4(), body=text, created_at=at, location_cell=cell)


class InMemoryPostRepository(InMemoryRepository[Post], PostRepository):
    """The posts in a dict, and the feed query done in Python."""

    def __init__(self, posts: Iterable[Post] = ()) -> None:
        super().__init__()
        for post in posts:
            self._items[post.id] = post

    async def page_neighbouring(
        self, *, cells: Iterable[str], before: datetime | None, limit: int
    ) -> list[Post]:
        wanted = set(cells)
        visible = [
            post
            for post in self._items.values()
            if post.location_cell in wanted
            and post.shows_in_locality_feed
            and (before is None or post.created_at < before)
        ]
        visible.sort(key=lambda post: post.created_at, reverse=True)
        return visible[:limit]


class FixedNeighbourhood(CellNeighbourhood):
    """A neighbourhood a test hands the rings itself, so no test depends on H3."""

    def __init__(self, rings: dict[str, set[str]] | None = None) -> None:
        self._rings = rings or {}

    def visible_from(self, cell: str, radius_km: float) -> set[str]:
        return self._rings.get(cell, {cell})


class FixedCells(CellStandard):
    """A cell standard that knows the cells a test named, and refuses every other string."""

    def __init__(self, known: Iterable[str] = ("here",)) -> None:
        self._known = set(known)

    def normalise(self, cell: str) -> str:
        if cell not in self._known:
            raise UnknownCellError(f"{cell!r} is not a cell here.")
        return cell


class FakePostsUnitOfWork(FakeUnitOfWork, PostsUnitOfWork):
    """A transaction whose posts are the ones a test passed in."""

    def __init__(self, posts: Iterable[Post] = ()) -> None:
        super().__init__()
        self.posts = InMemoryPostRepository(posts)
