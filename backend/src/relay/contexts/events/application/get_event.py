"""One event on its own, for a deep link, a shared one, or the page behind a list."""

from uuid import UUID

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
from relay.contexts.events.domain.event import EventNotFoundError
from relay.contexts.events.domain.listing import EventDetails


class GetEvent:
    """Fetches one event with the tally of who is going."""

    def __init__(self, uow: EventsUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, event_id: UUID) -> EventDetails:
        async with self._uow:
            event = await self._uow.events.get(event_id)
            if event is None:
                raise EventNotFoundError(f"No event {event_id} to show.")
            return EventDetails(event=event, rsvp_count=await self._uow.rsvps.count_for(event_id))
