"""Joining a community, which for a local one means being there."""

from uuid import UUID

from relay.contexts.communities.application.unit_of_work import CommunitiesUnitOfWork
from relay.contexts.communities.domain.community import (
    Community,
    CommunityNotFoundError,
    OutOfRangeError,
)
from relay.contexts.communities.domain.membership import Membership
from relay.contexts.communities.domain.ports import CellReach
from relay.contexts.posts.domain.ports import CellStandard
from relay.shared.application import Clock


class JoinCommunity:
    """Adds someone to a community's member list, if the community will have them.

    A community anchored somewhere is only for people standing in it: the whole point
    of a locality community is that everyone in it could walk to the same place. A
    community with no locality has no such rule, because there is no such thing as
    being the wrong distance from a subject.
    """

    def __init__(
        self,
        uow: CommunitiesUnitOfWork,
        clock: Clock,
        cells: CellStandard,
        reach: CellReach,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._cells = cells
        self._reach = reach

    async def execute(
        self,
        *,
        community_id: UUID,
        user_id: UUID,
        cell: str | None = None,
        pseudonym: str | None = None,
    ) -> Community:
        """`user_id` as a member of the community, counted, with the join committed.

        Returns the community rather than the membership because that is what the join
        screen redraws: how many are in it now, and that you are one of them.
        """
        async with self._uow:
            community = await self._seen(community_id, viewer=user_id)
            existing = await self._uow.members.find(community_id=community.id, user_id=user_id)
            if existing is not None:
                # Joining twice is the same button pressed twice. The membership they
                # already have is the answer, and their old pseudonym stays: changing it
                # is not what joining means.
                return community
            self._check_reaches(community, cell)
            membership = Membership.join(
                community,
                user_id=user_id,
                joined_at=self._clock.now(),
                pseudonym=pseudonym,
            )
            await self._uow.members.add(membership)
            await self._uow.commit()
            return await self._seen(community_id, viewer=user_id)

    async def _seen(self, community_id: UUID, *, viewer: UUID) -> Community:
        """The community as `viewer` sees it, counted. There is one, or there is nothing."""
        found = await self._uow.communities.get_for(community_id, viewer=viewer)
        if found is None:
            raise CommunityNotFoundError(f"No community {community_id} to join.")
        return found

    def _check_reaches(self, community: Community, cell: str | None) -> None:
        """Whether this reader is standing inside the community's locality."""
        if community.location_cell is None or community.radius_km is None:
            return
        named = cell.strip() if cell else ""
        if not named:
            raise OutOfRangeError(
                f"{community.name} is only for people nearby, and you have not said where you are."
            )
        standing = self._cells.normalise(named)
        if not self._reach.covers(
            anchor=community.location_cell,
            radius_km=community.radius_km,
            cell=standing,
        ):
            raise OutOfRangeError(f"{community.name} does not reach where you are standing.")
