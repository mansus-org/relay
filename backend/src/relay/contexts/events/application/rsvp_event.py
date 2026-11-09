"""Saying you are going to an event."""

from uuid import UUID

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
from relay.contexts.events.domain.event import Event, EventNotFoundError
from relay.contexts.events.domain.rsvp import AlreadyRsvpedError, Rsvp, RsvpOutcome
from relay.shared.application import Clock


class RsvpEvent:
    """Takes a member's place at an event.

    Saying it twice says it once: the second call changes nothing and is not an error,
    because the thing a person is doing when they tap a "going" button a second time
    is checking, not disagreeing with themselves.
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
                return await self._outcome(event, was_new=False)
            try:
                await self._uow.rsvps.add(
                    Rsvp.go(event_id=event_id, member_id=member_id, at=self._clock.now())
                )
                await self._uow.commit()
            except AlreadyRsvpedError:
                # Two taps at once: the unique index let one of them through, and the
                # other is the same place taken, not a second one.
                await self._uow.rollback()
                return await self._outcome(event, was_new=False)
            return await self._outcome(event, was_new=True)

    async def _outcome(self, event: Event, *, was_new: bool) -> RsvpOutcome:
        return RsvpOutcome(
            event=event, rsvp_count=await self._uow.rsvps.count_for(event.id), was_new=was_new
        )
