"""In-memory stand-ins for the posts ports, so a use-case test never touches a database."""

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from relay.contexts.posts.application.unit_of_work import PostsUnitOfWork
from relay.contexts.posts.domain.cells import UnknownCellError
from relay.contexts.posts.domain.ports import (
    CellNeighbourhood,
    CellStandard,
    PostRepository,
    ReactionRepository,
)
from relay.contexts.posts.domain.post import Post
from relay.contexts.posts.domain.reaction import Reaction, ReactionTally
from tests.fakes.repository import InMemoryRepository
from tests.fakes.unit_of_work import FakeUnitOfWork


def a_post(
    text: str = "A bar in my street closed.",
    *,
    cell: str | None = "here",
    at: datetime = datetime(2026, 1, 1, 12, tzinfo=UTC),
    author_id: UUID | None = None,
    parent_id: UUID | None = None,
) -> Post:
    """A post a test can name in one line."""
    return Post.write(
        author_id=author_id or uuid4(),
        body=text,
        created_at=at,
        location_cell=cell,
        parent_id=parent_id,
    )


def a_reaction(
    post: Post,
    emoji: str = "❤️",
    *,
    by: UUID | None = None,
    at: datetime = datetime(2026, 1, 1, 12, tzinfo=UTC),
) -> Reaction:
    """An emoji someone left on a post, with the post's own locality."""
    return Reaction.given(post_id=post.id, user_id=by or uuid4(), emoji=emoji, created_at=at)


class InMemoryPostRepository(InMemoryRepository[Post], PostRepository):
    """The posts in a dict, and the feed and thread queries done in Python."""

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

    async def replies_to(self, post_id: UUID) -> list[Post]:
        """A reply belongs to the post it answers, not to a locality, so moderation is
        the only thing that can hide one."""
        replies = [
            post for post in self._items.values() if post.parent_id == post_id and post.is_up
        ]
        replies.sort(key=lambda post: post.created_at)
        return replies

    async def count_replies(self, post_ids: Iterable[UUID]) -> dict[UUID, int]:
        counted: dict[UUID, int] = {}
        for post_id in post_ids:
            counted[post_id] = len(await self.replies_to(post_id))
        return counted


class InMemoryReactionRepository(ReactionRepository):
    """The reactions in a list, and the tally done in Python."""

    def __init__(self, reactions: Iterable[Reaction] = ()) -> None:
        self._items: list[Reaction] = list(reactions)

    async def add(self, reaction: Reaction) -> None:
        self._items.append(reaction)

    def _left_as(self, post_id: UUID, user_id: UUID, emoji: str) -> list[Reaction]:
        """That person's that emoji on that post, which is one reaction or none."""
        return [
            one
            for one in self._items
            if one.post_id == post_id and one.user_id == user_id and one.emoji == emoji
        ]

    async def get(self, *, post_id: UUID, user_id: UUID, emoji: str) -> Reaction | None:
        left = self._left_as(post_id, user_id, emoji)
        return left[0] if left else None

    async def remove(self, *, post_id: UUID, user_id: UUID, emoji: str) -> bool:
        left = self._left_as(post_id, user_id, emoji)
        if not left:
            return False
        self._items = [one for one in self._items if one not in left]
        return True

    async def tallies(
        self, post_ids: Iterable[UUID], *, viewer: UUID | None = None
    ) -> dict[UUID, tuple[ReactionTally, ...]]:
        tallies: dict[UUID, tuple[ReactionTally, ...]] = {}
        for post_id in post_ids:
            left: dict[str, list[Reaction]] = {}
            for one in self._items:
                if one.post_id == post_id:
                    left.setdefault(one.emoji, []).append(one)
            tallies[post_id] = tuple(
                ReactionTally(
                    emoji=emoji,
                    count=len(reactions),
                    user_reacted=any(one.user_id == viewer for one in reactions),
                )
                for emoji, reactions in left.items()
            )
        return {
            post_id: tuple(sorted(on_post, key=lambda tally: (-tally.count, tally.emoji)))
            for post_id, on_post in tallies.items()
        }


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
    """A transaction whose posts and reactions are the ones a test passed in."""

    def __init__(self, posts: Iterable[Post] = (), reactions: Iterable[Reaction] = ()) -> None:
        super().__init__()
        self.posts = InMemoryPostRepository(posts)
        self.reactions = InMemoryReactionRepository(reactions)
