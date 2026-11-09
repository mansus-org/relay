"""One community on its own: the screen that decides whether to join it."""

from uuid import UUID

from relay.contexts.communities.application.unit_of_work import CommunitiesUnitOfWork
from relay.contexts.communities.domain.community import Community, CommunityNotFoundError


class GetCommunity:
    """Fetches a community by id, for anybody.

    Public on purpose: a community you cannot read until you have joined it is one you
    have no way to decide whether to join. Only its feed is kept behind the membership.
    """

    def __init__(self, uow: CommunitiesUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, community_id: UUID, *, viewer: UUID | None = None) -> Community:
        async with self._uow:
            community = await self._uow.communities.get_for(community_id, viewer=viewer)
        if community is None:
            raise CommunityNotFoundError(f"No community {community_id} to show.")
        return community
