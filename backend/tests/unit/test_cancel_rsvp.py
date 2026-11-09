"""Giving a place back: the row goes, and so does the number on the event."""

from uuid import uuid4

import pytest

from relay.contexts.events.application import CancelRsvp
from relay.contexts.events.domain.event import EventNotFoundError
from relay.contexts.events.domain.rsvp import NotGoingError
from tests.fakes.events import FakeEventsUnitOfWork, an_event, going_to


def giving_back(uow: FakeEventsUnitOfWork) -> CancelRsvp:
    return CancelRsvp(uow=uow)


async def test_a_place_is_given_back_and_written_down() -> None:
    event = an_event()
    member = uuid4()
    uow = FakeEventsUnitOfWork([event], [going_to(event, member), going_to(event)])

    await giving_back(uow).execute(event_id=event.id, member_id=member)

    assert uow.committed is True
    assert await uow.rsvps.by_member(event_id=event.id, member_id=member) is None
    assert await uow.rsvps.count_for(event.id) == 1


async def test_an_event_that_was_never_planned_has_nothing_to_give_back() -> None:
    uow = FakeEventsUnitOfWork()

    with pytest.raises(EventNotFoundError):
        await giving_back(uow).execute(event_id=uuid4(), member_id=uuid4())

    assert uow.committed is False


async def test_a_place_that_was_never_taken_has_nothing_to_give_back() -> None:
    """Giving back a place you did not take is the same answer as a missing event."""
    event = an_event()
    uow = FakeEventsUnitOfWork([event], [going_to(event)])

    with pytest.raises(NotGoingError):
        await giving_back(uow).execute(event_id=event.id, member_id=uuid4())

    assert uow.committed is False
    assert await uow.rsvps.count_for(event.id) == 1


async def test_giving_it_back_twice_undoes_it_once() -> None:
    event = an_event()
    member = uuid4()
    uow = FakeEventsUnitOfWork([event], [going_to(event, member)])
    use_case = giving_back(uow)

    await use_case.execute(event_id=event.id, member_id=member)

    with pytest.raises(NotGoingError):
        await use_case.execute(event_id=event.id, member_id=member)
