"""One event on its own, for a deep link, a shared one, or the page behind a list."""

from uuid import UUID

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
from relay.contexts.events.domain.event import EventNotFoundError
from relay.contexts.events.domain.listing import EventDetails


class GetEvent:
    """Fetches one event with the tally of who is going.

    Reading an event is public; knowing whether *you* are going is not, so `member_id`
    is there when the caller has one and the answer is false when they do not.
    """

    def __init__(self, uow: EventsUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, event_id: UUID, member_id: UUID | None = None) -> EventDetails:
        async with self._uow:
            event = await self._uow.events.get(event_id)
            if event is None:
                raise EventNotFoundError(f"No event {event_id} to show.")
            going = (
                await self._uow.rsvps.by_member(event_id=event_id, member_id=member_id)
                if member_id is not None
                else None
            )
            names = (
                await self._uow.communities.names_for([event.community_id])
                if event.community_id is not None
                else {}
            )
            return EventDetails(
                event=event,
                rsvp_count=await self._uow.rsvps.count_for(event_id),
                user_rsvped=going is not None,
                community_name=names.get(event.community_id) if event.community_id else None,
            )
