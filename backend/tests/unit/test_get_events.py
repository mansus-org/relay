"""What is on: only this neighbourhood, soonest first, and paged without gaps."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from relay.contexts.events.application import GetEvents
from relay.contexts.events.domain.event import Event
from relay.contexts.events.domain.listing import UnknownPageError
from tests.fakes.clock import FixedClock
from tests.fakes.events import FakeEventsUnitOfWork, FixedNeighbourhood, an_event, going_to

# The reader is in "here". "next-door" is inside their radius, "elsewhere" is not.
NEIGHBOURHOOD = FixedNeighbourhood({"here": {"here", "next-door"}, "far": {"far"}})
NOW = datetime(2026, 3, 4, 12, tzinfo=UTC)
TOKYO = timezone(timedelta(hours=9))


def planned(*titles: str, cell: str | None = "here", from_: int = 1) -> list[Event]:
    """Events in the reader's own cell, soonest first, an hour apart from now."""
    return [
        an_event(title, cell=cell, starts_at=NOW + timedelta(hours=from_ + index))
        for index, title in enumerate(titles)
    ]


async def read(uow: FakeEventsUnitOfWork, from_: str | None = None):
    return await GetEvents(uow=uow, neighbourhood=NEIGHBOURHOOD, clock=FixedClock(NOW)).execute(
        cell="here", radius_km=10, from_=from_
    )


async def test_the_next_event_is_first() -> None:
    uow = FakeEventsUnitOfWork(planned("sooner", "later", from_=2))

    page = await read(uow)

    assert [details.event.title for details in page.events] == ["sooner", "later"]


async def test_an_event_that_has_already_started_is_not_in_the_list() -> None:
    """A list of what is on is a list of what is still to come."""
    uow = FakeEventsUnitOfWork(
        [
            an_event("tomorrow", starts_at=NOW + timedelta(days=1)),
            an_event("ten minutes ago", starts_at=NOW - timedelta(minutes=10)),
        ]
    )

    page = await read(uow)

    assert [details.event.title for details in page.events] == ["tomorrow"]


async def test_an_event_outside_the_radius_is_not_in_the_list() -> None:
    uow = FakeEventsUnitOfWork([*planned("here"), *planned("elsewhere", cell="elsewhere")])

    page = await read(uow)

    assert [details.event.title for details in page.events] == ["here"]


async def test_an_event_in_a_neighbouring_cell_is_in_the_list() -> None:
    uow = FakeEventsUnitOfWork(planned("next door", cell="next-door"))

    page = await read(uow)

    assert [details.event.title for details in page.events] == ["next door"]


async def test_an_event_that_never_said_where_it_is_is_in_no_localitys_list() -> None:
    uow = FakeEventsUnitOfWork([*planned("here"), *planned("nowhere in particular", cell=None)])

    page = await read(uow)

    assert [details.event.title for details in page.events] == ["here"]


async def test_every_event_carries_how_many_are_going_to_it() -> None:
    booked = an_event("Book club", starts_at=NOW + timedelta(hours=1))
    alone = an_event("Silent reading", starts_at=NOW + timedelta(hours=2))
    uow = FakeEventsUnitOfWork(
        [booked, alone],
        rsvps=[going_to(booked, uuid4()), going_to(booked, uuid4())],
    )

    page = await read(uow)

    assert [(details.event.title, details.rsvp_count) for details in page.events] == [
        ("Book club", 2),
        ("Silent reading", 0),
    ]


async def test_a_page_is_a_page_and_not_the_whole_calendar() -> None:
    uow = FakeEventsUnitOfWork(
        [
            an_event(f"event {index}", starts_at=NOW + timedelta(hours=index + 1))
            for index in range(25)
        ]
    )

    page = await read(uow)

    assert len(page.events) == 20
    assert page.next_from.at == NOW + timedelta(hours=20)
    assert page.next_from.seen_id == page.events[-1].event.id


async def test_the_last_page_promises_no_more() -> None:
    uow = FakeEventsUnitOfWork(planned("only one"))

    page = await read(uow)

    assert page.next_from is None


async def test_walking_the_pages_sees_every_event_once() -> None:
    uow = FakeEventsUnitOfWork(
        [
            an_event(f"event {index}", starts_at=NOW + timedelta(hours=index + 1))
            for index in range(25)
        ]
    )

    first = await read(uow)
    second = await read(uow, from_=first.next_from.as_text())

    seen = [details.event.title for details in first.events + second.events]
    assert len(seen) == 25
    assert len(set(seen)) == 25
    assert second.next_from is None


async def test_events_that_all_start_at_the_same_time_still_come_out_a_page_at_a_time() -> None:
    """Hosts pick start times, and a town's events all start at seven.

    Twenty of them can share one `starts_at`, and a marker that named only the instant
    would resume after all twenty: the ones that did not fit on the page would never be
    on any page. The marker names a row, so they come out in order like any other.
    """
    seven = NOW + timedelta(hours=7)
    uow = FakeEventsUnitOfWork([an_event(f"choir {index}", starts_at=seven) for index in range(25)])

    first = await read(uow)
    second = await read(uow, from_=first.next_from.as_text())

    seen = [details.event.title for details in first.events + second.events]
    assert len(seen) == 25
    assert len(set(seen)) == 25


async def test_a_marker_no_page_ever_handed_out_is_refused() -> None:
    """A `from` made up rather than handed back is the client's mistake to hear about."""
    uow = FakeEventsUnitOfWork(planned("one"))

    with pytest.raises(UnknownPageError):
        await read(uow, from_="2026-03-04T18:00:00Z~not-the-row-it-stopped-on")


async def test_the_page_starts_at_the_instant_it_was_asked_for() -> None:
    """The event that starts at the wall is on the page: `from` is where the reading picks up."""
    uow = FakeEventsUnitOfWork(planned("one", "two", "three"))

    page = await read(uow, from_=str(NOW + timedelta(hours=2)))

    assert [details.event.title for details in page.events] == ["two", "three"]


async def test_the_page_starts_at_the_same_instant_when_the_date_comes_in_another_zone() -> None:
    """`from` is an instant, not a wall-clock reading, whichever way it was written."""
    uow = FakeEventsUnitOfWork(planned("one", "two", "three"))

    in_tokyo = (NOW + timedelta(hours=2)).astimezone(TOKYO).isoformat()
    page = await read(uow, from_=in_tokyo)

    assert [details.event.title for details in page.events] == ["two", "three"]


async def test_a_page_that_names_no_start_reads_from_now() -> None:
    """The default is the clock, so an event tonight is here and one last week is not."""
    uow = FakeEventsUnitOfWork(
        [
            an_event("tonight", starts_at=NOW + timedelta(hours=6)),
            an_event("last week", starts_at=NOW - timedelta(days=7)),
        ]
    )

    page = await read(uow)

    assert [details.event.title for details in page.events] == ["tonight"]


async def test_a_page_asked_for_the_past_reads_the_recent_past_first() -> None:
    """`from=past` is the only way to ask, and it reads back from now, not up from the
    first thing ever filed: the last thing that happened is what a person wants first.

    What has not started is not part of the past, so the one still to come is not here.
    """
    uow = FakeEventsUnitOfWork(
        [
            an_event("last week", starts_at=NOW - timedelta(days=7)),
            an_event("yesterday", starts_at=NOW - timedelta(days=1)),
            an_event("tonight", starts_at=NOW + timedelta(hours=6)),
        ]
    )

    page = await read(uow, from_="past")

    assert [details.event.title for details in page.events] == ["yesterday", "last week"]


async def test_walking_the_pages_backwards_sees_the_past_once() -> None:
    uow = FakeEventsUnitOfWork(
        [
            an_event(f"event {index}", starts_at=NOW - timedelta(hours=index + 1))
            for index in range(25)
        ]
    )

    first = await read(uow, from_="past")
    second = await read(uow, from_=first.next_from.as_text())

    seen = [details.event.title for details in first.events + second.events]
    assert len(seen) == 25
    assert len(set(seen)) == 25
    assert second.next_from is None


async def test_a_marker_from_the_past_keeps_reading_backwards() -> None:
    """Passing `next_from` back is one string and one instruction: the direction travels
    in it, or the second page would read forwards from where the first one stopped."""
    uow = FakeEventsUnitOfWork(
        [
            an_event(f"event {index}", starts_at=NOW - timedelta(hours=index + 1))
            for index in range(21)
        ]
    )

    first = await read(uow, from_="past")
    second = await read(uow, from_=first.next_from.as_text())

    assert first.next_from.backwards is True
    assert second.events[0].event.starts_at < first.events[-1].event.starts_at


async def test_a_date_without_a_time_is_that_midnight() -> None:
    """A person typing a date means the day, and the day starts at midnight."""
    uow = FakeEventsUnitOfWork(
        [
            an_event("the night before", starts_at=datetime(2026, 3, 3, 23, tzinfo=UTC)),
            an_event("the morning of", starts_at=datetime(2026, 3, 4, 0, 30, tzinfo=UTC)),
        ]
    )

    page = await read(uow, from_="2026-03-04")

    assert [details.event.title for details in page.events] == ["the morning of"]
