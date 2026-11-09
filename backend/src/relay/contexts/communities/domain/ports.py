"""Ports the communities context needs; infrastructure supplies the implementations."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from datetime import datetime
from uuid import UUID

from relay.contexts.communities.domain.community import Community
from relay.contexts.communities.domain.membership import Membership
from relay.contexts.posts.domain.post import Post
from relay.shared.domain import Repository


class CommunityRepository(Repository[Community, UUID]):
    """Communities by id, and the ones anchored near a reader."""

    @abstractmethod
    async def get_for(self, id: UUID, *, viewer: UUID | None) -> Community | None:
        """One community, with `member_count` and `is_member` filled in for `viewer`."""

    @abstractmethod
    async def slug_taken(self, slug: str) -> bool:
        """Whether some other community already answers to that slug."""

    @abstractmethod
    async def list_anchored(self, *, viewer: UUID | None) -> list[Community]:
        """Every community with a locality, newest first, counted for `viewer`.

        The reach test is not in here: each community has its own radius, so there is
        no one SQL predicate that covers them all and the caller asks about each one.
        """


class MembershipRepository(Repository[Membership, UUID]):
    """Who belongs to which community, and what they are called there."""

    @abstractmethod
    async def find(self, *, community_id: UUID, user_id: UUID) -> Membership | None:
        """That person's membership of that community, if they have one."""

    @abstractmethod
    async def pseudonyms(self, *, community_id: UUID, user_ids: Iterable[UUID]) -> dict[UUID, str]:
        """What each of `user_ids` is called in `community`.

        Only the ones with a pseudonym: everyone else is called by their own name, and
        a dict with a `None` in it for every member would just invite a mistake.
        """


class CommunityFeedReader(ABC):
    """The posts a community's members have said.

    The posts table belongs to the posts context; this reads it and never writes it.
    """

    @abstractmethod
    async def page(
        self, *, community_id: UUID, before: datetime | None, limit: int
    ) -> Sequence[Post]:
        """Newest first: posts filed under `community_id`, not removed, older than `before`."""


class CellReach(ABC):
    """Whether a community's locality covers the cell a reader is standing in."""

    @abstractmethod
    def covers(self, *, anchor: str, radius_km: float, cell: str) -> bool:
        """Is `cell` within `radius_km` of `anchor`?

        The same question the locality feed answers with a k-ring, asked about one cell
        instead of a reader's whole neighbourhood: a community anchored at Vigo with a
        5 km radius is joinable from the port and not from Pontevedra.
        """
