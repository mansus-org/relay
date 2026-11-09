"""Ports the posts context needs; infrastructure supplies the implementations."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from relay.contexts.posts.domain.post import Post
from relay.contexts.posts.domain.reaction import Reaction, ReactionTally
from relay.shared.domain import Repository


class PostRepository(Repository[Post, UUID]):
    """Posts by id, the newest ones still up around a cell, and the replies under one."""

    @abstractmethod
    async def page_neighbouring(
        self, *, cells: Iterable[str], before: datetime | None, limit: int
    ) -> list[Post]:
        """Newest first: posts inside one of `cells`, not removed, older than `before`.

        A post with no `location_cell` is in none of the cells and so never comes back.
        """

    @abstractmethod
    async def replies_to(self, post_id: UUID) -> list[Post]:
        """Oldest first: the posts said in reply to this one.

        One level only - a reply to a reply is another call away, which is what lets
        the client draw a thread as deep as it likes. A removed reply is not here.
        """

    @abstractmethod
    async def count_replies(self, post_ids: Iterable[UUID]) -> dict[UUID, int]:
        """How many replies each of these posts has, removed ones not counted.

        Every post asked for is answered; one nobody answered counts none.
        """


class ReactionRepository(ABC):
    """The emoji people leave on posts: one per person, per emoji, per post."""

    @abstractmethod
    async def add(self, reaction: Reaction) -> None:
        """Put one person's emoji on a post.

        The same person, the same emoji, the same post twice is refused: it is one
        opinion said twice, not two of them.
        """

    @abstractmethod
    async def get(self, *, post_id: UUID, user_id: UUID, emoji: str) -> Reaction | None:
        """That person's reaction with that emoji on that post, if they left one."""

    @abstractmethod
    async def remove(self, *, post_id: UUID, user_id: UUID, emoji: str) -> bool:
        """Take that reaction back. False when there was none to take."""

    @abstractmethod
    async def tallies(
        self, post_ids: Iterable[UUID], *, viewer: UUID | None = None
    ) -> dict[UUID, tuple[ReactionTally, ...]]:
        """Every emoji on each of these posts, counted, the most-used first.

        `viewer` is who is reading: an emoji they left comes back marked. Every post
        asked for is answered; one nobody reacted to has no emoji on it.
        """


class CellNeighbourhood(ABC):
    """The cells a reader standing in `cell` can see posts from, `radius_km` out."""

    @abstractmethod
    def visible_from(self, cell: str, radius_km: float) -> set[str]: ...


class CellStandard(ABC):
    """Which strings count as a cell here, and the one way a cell is written."""

    @abstractmethod
    def normalise(self, cell: str) -> str:
        """The form of `cell` that the feed will read back.

        Raises UnknownCellError for anything it would never read: a string that is not
        a cell, or one at a resolution no feed is served at. Saving either would hand
        the writer a post no locality can ever show.
        """


class LiveFeed(ABC):
    """Whoever is reading a locality right now, told about a post the moment it is said."""

    @abstractmethod
    def announce(self, post: Post) -> None:
        """Tell every reader watching where `post` was said that it now exists.

        Called once the post is saved, and never waits: a reader whose signal is bad
        must not be able to hold up the person who just said something. A post with no
        locality is in no locality, so it reaches nobody.
        """


class NoLiveFeed(LiveFeed):
    """A locality nobody is watching: the default when nothing is wired up to listen."""

    def announce(self, post: Post) -> None:
        """Nothing to tell, because nobody is there to be told."""
