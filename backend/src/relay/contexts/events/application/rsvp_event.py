"""Saying you are going to an event."""

from uuid import UUID

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
from relay.contexts.events.domain.event import EventNotFoundError
from relay.contexts.events.domain.rsvp import AlreadyRsvpedError, Rsvp, RsvpOutcome
from relay.shared.application import Clock


class RsvpEvent:
    """Takes a member's place at an event.

    One place per person, so a second tap is a conflict and not a quiet success. What
    comes back is `RsvpOutcome`, and its tally is read after the write.
    """

    def __init__(self, uow: EventsUnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, *, event_id: UUID, member_id: UUID) -> RsvpOutcome:
        async with self._uow:
            event = await self._uow.events.get(event_id)
            if event is None:
                raise EventNotFoundError(f"No event {event_id} to go to.")
            if await self._uow.rsvps.by_member(event_id=event_id, member_id=member_id) is not None:
                raise AlreadyRsvpedError(f"You are already going to event {event_id}.")
            await self._uow.rsvps.add(
                Rsvp.go(event_id=event_id, member_id=member_id, at=self._clock.now())
            )
            await self._uow.commit()
            # Counted after the commit, so this place is inside the number.
            return RsvpOutcome(event=event, rsvp_count=await self._uow.rsvps.count_for(event.id))
