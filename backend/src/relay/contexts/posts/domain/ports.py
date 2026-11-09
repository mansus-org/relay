"""Ports the posts context needs; infrastructure supplies the implementations."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from relay.contexts.posts.domain.post import Post
from relay.shared.domain import Repository


class PostRepository(Repository[Post, UUID]):
    """Posts by id, and the newest ones still up around a cell."""

    @abstractmethod
    async def page_neighbouring(
        self, *, cells: Iterable[str], before: datetime | None, limit: int
    ) -> list[Post]:
        """Newest first: posts inside one of `cells`, not removed, older than `before`.

        A post with no `location_cell` is in none of the cells and so never comes back.
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
