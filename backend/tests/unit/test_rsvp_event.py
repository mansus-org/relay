"""Saying you are going: one place taken, or the race that took it a moment earlier."""

from uuid import UUID, uuid4

import pytest

from relay.contexts.events.application import RsvpEvent
from relay.contexts.events.domain.event import Event, EventNotFoundError
from relay.contexts.events.domain.rsvp import AlreadyRsvpedError, Rsvp
from tests.fakes.clock import FixedClock
from tests.fakes.events import (
    PLANNED,
    FakeEventsUnitOfWork,
    InMemoryRsvpRepository,
    an_event,
    going_to,
)

NOW = PLANNED


def saying(uow: FakeEventsUnitOfWork) -> RsvpEvent:
    return RsvpEvent(uow=uow, clock=FixedClock(NOW))


class RaceLost(InMemoryRsvpRepository):
    """The repository where the other tap slipped its row in between the check and the write."""

    def __init__(self, event: Event, member_id: UUID) -> None:
        super().__init__()
        self._event_id = event.id
        self._member_id = member_id
        self._raced = False

    async def add(self, entity: Rsvp) -> None:
        if not self._raced:
            self._raced = True
            await super().add(Rsvp.go(event_id=self._event_id, member_id=self._member_id, at=NOW))
            raise AlreadyRsvpedError("Somebody took this place a moment ago.")
        await super().add(entity)


async def test_a_place_is_taken_and_written_down() -> None:
    event = an_event()
    uow = FakeEventsUnitOfWork([event])
    member = uuid4()

    outcome = await saying(uow).execute(event_id=event.id, member_id=member)

    assert uow.committed is True
    assert outcome.event is event
    assert outcome.rsvp_count == 1
    assert outcome.was_new is True
    taken = await uow.rsvps.by_member(event_id=event.id, member_id=member)
    assert taken is not None
    assert taken.created_at == NOW


async def test_saying_it_twice_takes_one_place_and_is_not_an_error() -> None:
    """The second tap is checking, not disagreeing with yourself."""
    event = an_event()
    member = uuid4()
    uow = FakeEventsUnitOfWork([event], [going_to(event, member)])

    outcome = await saying(uow).execute(event_id=event.id, member_id=member)

    assert outcome.was_new is False
    assert outcome.rsvp_count == 1
    assert uow.committed is False


async def test_everyone_who_said_it_is_counted() -> None:
    event = an_event()
    uow = FakeEventsUnitOfWork([event], [going_to(event), going_to(event)])

    outcome = await saying(uow).execute(event_id=event.id, member_id=uuid4())

    assert outcome.rsvp_count == 3
    assert outcome.was_new is True


async def test_there_is_nothing_to_go_to_that_was_never_planned() -> None:
    uow = FakeEventsUnitOfWork()

    with pytest.raises(EventNotFoundError):
        await saying(uow).execute(event_id=uuid4(), member_id=uuid4())

    assert uow.committed is False


async def test_two_taps_at_once_take_one_place() -> None:
    """The unique index decides between them, and losing that race is not an error."""
    event = an_event()
    member = uuid4()
    uow = FakeEventsUnitOfWork([event])
    uow.rsvps = RaceLost(event, member)

    outcome = await saying(uow).execute(event_id=event.id, member_id=member)

    assert outcome.was_new is False
    assert outcome.rsvp_count == 1
    assert uow.rolled_back is True
