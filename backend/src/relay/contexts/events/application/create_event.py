"""Planning an event and writing it down."""

from datetime import datetime
from uuid import UUID

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
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
        )
        async with self._uow:
            await self._uow.events.add(event)
            await self._uow.commit()
        return event

    def _filed_under(self, cell: str | None) -> str | None:
        """Where it is happening, in the form a list of events reads back.

        Nothing is filed under a string no list will ever ask for: an event saved as
        `883920CD1BFFFFF`, or at the wrong resolution, is an event its host will never
        see again. Refusing that write is kinder than a 201 and silence. No cell at all
        stays allowed, because that is a host choosing not to say where it is yet.
        """
        named = cell.strip() if cell else ""
        return self._cells.normalise(named) if named else None
