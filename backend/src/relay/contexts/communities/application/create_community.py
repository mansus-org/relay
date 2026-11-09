"""Founding a community."""

from uuid import UUID

from relay.contexts.communities.application.unit_of_work import CommunitiesUnitOfWork
from relay.contexts.communities.domain.community import Community
from relay.contexts.posts.domain.ports import CellStandard
from relay.shared.application import Clock


class CreateCommunity:
    """Founds a community and saves it.

    The founder is not made a member of it. They asked for a community to exist, which
    is not the same as asking to be on its member list, and RELY-91's screens will want
    the difference.
    """

    def __init__(self, uow: CommunitiesUnitOfWork, clock: Clock, cells: CellStandard) -> None:
        self._uow = uow
        self._clock = clock
        self._cells = cells

    async def execute(
        self,
        *,
        created_by: UUID,
        name: str,
        description: str = "",
        location_cell: str | None = None,
        radius_km: float | None = None,
        allow_pseudonyms: bool = False,
    ) -> Community:
        community = Community.start(
            name=name,
            created_by=created_by,
            created_at=self._clock.now(),
            description=description,
            location_cell=self._anchored_at(location_cell),
            radius_km=radius_km,
            allow_pseudonyms=allow_pseudonyms,
        )
        async with self._uow:
            if await self._uow.communities.slug_taken(community.slug):
                # Two "Book Club"s is an ordinary thing for two towns to have. Two slugs
                # is not, and the id this community already has is the shortest thing
                # available to tell them apart by.
                community = community.model_copy(
                    update={"slug": f"{community.slug}-{str(community.id)[:8]}"}
                )
            await self._uow.communities.add(community)
            await self._uow.commit()
        return community

    def _anchored_at(self, cell: str | None) -> str | None:
        """Where it is, in the form the reach test reads back.

        Refuses a cell no reach test could answer about, rather than founding a
        community that is anchored nowhere and quietly missing from every nearby list.
        """
        named = cell.strip() if cell else ""
        return self._cells.normalise(named) if named else None
