"""Planning an event and writing it down."""

from datetime import datetime
from uuid import UUID

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
from relay.contexts.events.domain.community import CommunityNotFoundError, NotAMemberError
from relay.contexts.events.domain.event import Event
from relay.contexts.events.domain.ports import CellStandard
from relay.shared.application import Clock


class CreateEvent:
    """Plans an event and saves it. The clock is injected so a test knows when it was planned."""

    def __init__(self, uow: EventsUnitOfWork, clock: Clock, cells: CellStandard) -> None:
        self._uow = uow
        self._clock = clock
        self._cells = cells

    async def execute(
        self,
        *,
        host_id: UUID,
        title: str,
        starts_at: datetime | str,
        ends_at: datetime | str | None = None,
        venue_name: str | None = None,
        details: str | None = None,
        location_cell: str | None = None,
        community_id: UUID | None = None,
    ) -> Event:
        event = Event.plan(
            host_id=host_id,
            title=title,
            starts_at=starts_at,
            created_at=self._clock.now(),
            ends_at=ends_at,
            venue_name=venue_name,
            details=details,
            location_cell=self._filed_under(location_cell),
            community_id=community_id,
        )
        async with self._uow:
            if community_id is not None:
                await self._belonging_to(host_id, community_id)
            await self._uow.events.add(event)
            await self._uow.commit()
        return event

    async def _belonging_to(self, host_id: UUID, community_id: UUID) -> None:
        """Check the host is one of the people this event would be filed under.

        An event filed under a community is on that community's list, where every one of
        its members will read it, so a stranger cannot put one there. A community that
        does not exist fails the same test and is said plainly: a host following a link
        copied out of a note deserves to be told which half of it was wrong.
        """
        if not await self._uow.communities.names_for([community_id]):
            raise CommunityNotFoundError(f"No community {community_id} to file an event under.")
        going = await self._uow.communities.is_member(community_id=community_id, member_id=host_id)
        if not going:
            raise NotAMemberError("Only members can plan an event for a community.")

    def _filed_under(self, cell: str | None) -> str | None:
        """Where it is happening, in the form a list of events reads back.

        Nothing is filed under a string no list will ever ask for: an event saved as
        `883920CD1BFFFFF`, or at the wrong resolution, is an event its host will never
        see again. Refusing that write is kinder than a 201 and silence. No cell at all
        stays allowed, because that is a host choosing not to say where it is yet.
        """
        named = cell.strip() if cell else ""
        return self._cells.normalise(named) if named else None
