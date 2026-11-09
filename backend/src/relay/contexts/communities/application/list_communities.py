"""The nearby list: the communities whose locality the reader is standing in."""

from collections.abc import Sequence
from uuid import UUID

from relay.contexts.communities.application.unit_of_work import CommunitiesUnitOfWork
from relay.contexts.communities.domain.community import Community
from relay.contexts.communities.domain.ports import CellReach
from relay.contexts.posts.domain.ports import CellStandard


class ListCommunities:
    """Every community that reaches the cell the reader is in.

    The reach test runs per community rather than in SQL because each community has
    its own radius: one reader, one cell, and a hundred different circles to test it
    against. A node holds tens of communities, not tens of thousands, so the loop is
    the cheapest thing here and the one that can actually answer the question.
    """

    def __init__(self, uow: CommunitiesUnitOfWork, cells: CellStandard, reach: CellReach) -> None:
        self._uow = uow
        self._cells = cells
        self._reach = reach

    async def execute(self, *, cell: str, viewer: UUID | None = None) -> Sequence[Community]:
        named = self._cells.normalise(cell)
        async with self._uow:
            found = await self._uow.communities.list_anchored(viewer=viewer)
        return tuple(community for community in found if self._reaches(community, named))

    def _reaches(self, community: Community, cell: str) -> bool:
        """Whether this community is somewhere the reader is.

        A community with no locality reaches nobody: it is about a subject, and the
        only way into it is a link someone shared.
        """
        if community.location_cell is None or community.radius_km is None:
            return False
        return self._reach.covers(
            anchor=community.location_cell, radius_km=community.radius_km, cell=cell
        )
