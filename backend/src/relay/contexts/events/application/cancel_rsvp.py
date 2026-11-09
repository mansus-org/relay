"""Giving a place back."""

from uuid import UUID

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
from relay.contexts.events.domain.event import EventNotFoundError
from relay.contexts.events.domain.rsvp import NotGoingError


class CancelRsvp:
    """Gives a member's place at an event back.

    Two different questions and one answer: an event that does not exist and a place
    that was never taken are both "there is nothing here to give back", and a client
    that retries a delete it already succeeded at hears that rather than silence.
    """

    def __init__(self, uow: EventsUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, *, event_id: UUID, member_id: UUID) -> None:
        async with self._uow:
            if await self._uow.events.get(event_id) is None:
                raise EventNotFoundError(f"No event {event_id} to leave.")
            place = await self._uow.rsvps.by_member(event_id=event_id, member_id=member_id)
            if place is None:
                raise NotGoingError(f"You are not going to event {event_id}.")
            await self._uow.rsvps.delete(place)
            await self._uow.commit()
