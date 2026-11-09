"""One event read back on its own, with how many are going to it."""

from uuid import uuid4

import pytest

from relay.contexts.events.application import GetEvent
from relay.contexts.events.domain.event import EventNotFoundError
from tests.fakes.events import FakeEventsUnitOfWork, an_event, going_to


async def test_one_event_on_its_own_carries_its_own_tally() -> None:
    booked = an_event("Book club")
    other = an_event("Silent reading")
    uow = FakeEventsUnitOfWork(
        [booked, other], [going_to(booked), going_to(booked), going_to(other)]
    )

    details = await GetEvent(uow=uow).execute(booked.id)

    assert details.event.title == "Book club"
    assert details.rsvp_count == 2


async def test_an_event_nobody_is_going_to_says_so() -> None:
    event = an_event()

    details = await GetEvent(uow=FakeEventsUnitOfWork([event])).execute(event.id)

    assert details.event is event
    assert details.rsvp_count == 0


async def test_an_event_that_was_never_planned_is_not_there() -> None:
    with pytest.raises(EventNotFoundError):
        await GetEvent(uow=FakeEventsUnitOfWork()).execute(uuid4())
