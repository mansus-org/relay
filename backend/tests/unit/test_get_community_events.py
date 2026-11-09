"""A community's list: its own events only, soonest first, and paged the same way."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from relay.contexts.events.application import GetCommunityEvents
from relay.contexts.events.domain.community import CommunityNotFoundError
from relay.contexts.events.domain.event import Event
from relay.contexts.events.domain.listing import UnknownPageError
from tests.fakes.clock import FixedClock
from tests.fakes.events import (
    FakeEventsUnitOfWork,
    FixedNeighbourhood,
    InMemoryCommunities,
    an_event,
    going_to,
)

NOW = datetime(2026, 3, 4, 12, tzinfo=UTC)
# The reader stands in "here"; "far" is a cell nobody nearby can see. Same ring as every
# other list, because a community being people does not lift it.
NEIGHBOURHOOD = FixedNeighbourhood({"here": {"here"}, "far": {"far"}})
BOOK_CLUB = UUID("11111111-1111-1111-1111-111111111111")
CHOIR = UUID("22222222-2222-2222-2222-222222222222")


def a_community(*ids: UUID) -> InMemoryCommunities:
    """The communities these tests name, with no members — reading a list needs none."""
    found = InMemoryCommunities()
    for community_id in ids or (BOOK_CLUB,):
        found.found(community_id, f"The {community_id.hex[:8]}")
    return found


def planned(*titles: str, community_id: UUID = BOOK_CLUB, from_: int = 1) -> list[Event]:
    """Events filed under one community, soonest first, an hour apart from now."""
    return [
        an_event(title, community_id=community_id, starts_at=NOW + timedelta(hours=from_ + index))
        for index, title in enumerate(titles)
    ]


def reading(uow: FakeEventsUnitOfWork, community_id: UUID = BOOK_CLUB):
    use_case = GetCommunityEvents(uow=uow, neighbourhood=NEIGHBOURHOOD, clock=FixedClock(NOW))
    return use_case.execute(community_id=community_id, cell="here", from_=None)


def a_calendar(count: int, *, back: bool = False) -> list[Event]:
    """`count` events an hour apart, for the tests that have to walk more than one page.

    `back` puts them in the past instead, which is the other direction the marker reads.
    """
    hours = -1 if back else 1
    return [
        an_event(
            f"event {index}",
            community_id=BOOK_CLUB,
            starts_at=NOW + timedelta(hours=hours * (index + 1)),
        )
        for index in range(count)
    ]


async def read(uow: FakeEventsUnitOfWork, community_id: UUID = BOOK_CLUB, from_: str | None = None):
    use_case = GetCommunityEvents(uow=uow, neighbourhood=NEIGHBOURHOOD, clock=FixedClock(NOW))
    return await use_case.execute(community_id=community_id, cell="here", from_=from_)


async def test_the_next_event_is_first() -> None:
    uow = FakeEventsUnitOfWork(planned("sooner", "later", from_=2), communities=a_community())

    page = await read(uow)

    assert [details.event.title for details in page.events] == ["sooner", "later"]


async def test_an_event_that_has_already_started_is_not_in_the_list() -> None:
    """The same rule as the locality's list: what is on is what is still to come."""
    uow = FakeEventsUnitOfWork(
        [
            an_event("tomorrow", community_id=BOOK_CLUB, starts_at=NOW + timedelta(days=1)),
            an_event("last week", community_id=BOOK_CLUB, starts_at=NOW - timedelta(days=7)),
        ],
        communities=a_community(),
    )

    page = await read(uow)

    assert [details.event.title for details in page.events] == ["tomorrow"]


async def test_another_communitys_event_is_not_on_this_list() -> None:
    uow = FakeEventsUnitOfWork(
        [*planned("ours"), *planned("theirs", community_id=CHOIR)],
        communities=a_community(BOOK_CLUB, CHOIR),
    )

    page = await read(uow)

    assert [details.event.title for details in page.events] == ["ours"]


async def test_an_event_that_belongs_to_no_community_is_on_nobody_s_list() -> None:
    """A plan filed under a place alone stays a place's plan."""
    uow = FakeEventsUnitOfWork(
        [*planned("ours"), an_event("just a place", community_id=None)],
        communities=a_community(),
    )

    page = await read(uow)

    assert [details.event.title for details in page.events] == ["ours"]


async def test_the_ring_applies_here_the_way_it_does_everywhere() -> None:
    """Membership is whose list you may add to, not what you are allowed to see.

    The plan filed an hour away is invisible to the member an hour away from it, and so
    is the one nobody has given a place yet: an event is visible where its cell is, and
    one with no cell is nowhere. Both are the ticket's locality rule, not a courtesy.
    """
    uow = FakeEventsUnitOfWork(
        [
            an_event(
                "in the hall",
                community_id=BOOK_CLUB,
                cell="here",
                starts_at=NOW + timedelta(hours=1),
            ),
            an_event(
                "no venue yet",
                community_id=BOOK_CLUB,
                cell=None,
                starts_at=NOW + timedelta(hours=2),
            ),
            an_event(
                "somewhere else",
                community_id=BOOK_CLUB,
                cell="far",
                starts_at=NOW + timedelta(hours=3),
            ),
        ],
        communities=a_community(),
    )

    page = await read(uow)

    assert [details.event.title for details in page.events] == ["in the hall"]


async def test_every_event_carries_how_many_are_going_to_it() -> None:
    booked = an_event("Book club", community_id=BOOK_CLUB, starts_at=NOW + timedelta(hours=1))
    alone = an_event("Silent reading", community_id=BOOK_CLUB, starts_at=NOW + timedelta(hours=2))
    uow = FakeEventsUnitOfWork(
        [booked, alone],
        rsvps=[going_to(booked, uuid4()), going_to(booked, uuid4())],
        communities=a_community(),
    )

    page = await read(uow)

    assert [(details.event.title, details.rsvp_count) for details in page.events] == [
        ("Book club", 2),
        ("Silent reading", 0),
    ]


async def test_every_event_carries_the_name_of_the_community_it_is_on() -> None:
    """The list is read one community at a time, and still says who it was read for."""
    uow = FakeEventsUnitOfWork(planned("Book swap"), communities=a_community(BOOK_CLUB))

    page = await read(uow)

    assert page.events[0].community_name == "The 11111111"


async def test_a_page_is_a_page_and_not_the_whole_calendar() -> None:
    uow = FakeEventsUnitOfWork(
        a_calendar(25),
        communities=a_community(),
    )

    page = await read(uow)

    assert len(page.events) == 20
    assert page.next_from.at == NOW + timedelta(hours=20)
    assert page.next_from.seen_id == page.events[-1].event.id


async def test_walking_the_pages_sees_every_event_once() -> None:
    uow = FakeEventsUnitOfWork(
        a_calendar(25),
        communities=a_community(),
    )

    first = await read(uow)
    second = await read(uow, from_=first.next_from.as_text())

    seen = [details.event.title for details in first.events + second.events]
    assert len(seen) == 25
    assert len(set(seen)) == 25
    assert second.next_from is None


async def test_a_page_asked_for_the_past_reads_the_recent_past_first() -> None:
    """`from=past` is the same word as on the locality's list, and means the same here."""
    uow = FakeEventsUnitOfWork(
        [
            an_event("last week", community_id=BOOK_CLUB, starts_at=NOW - timedelta(days=7)),
            an_event("yesterday", community_id=BOOK_CLUB, starts_at=NOW - timedelta(days=1)),
            an_event("tonight", community_id=BOOK_CLUB, starts_at=NOW + timedelta(hours=6)),
        ],
        communities=a_community(),
    )

    page = await read(uow, from_="past")

    assert [details.event.title for details in page.events] == ["yesterday", "last week"]


async def test_a_marker_from_the_past_keeps_reading_backwards() -> None:
    uow = FakeEventsUnitOfWork(
        a_calendar(21, back=True),
        communities=a_community(),
    )

    first = await read(uow, from_="past")
    second = await read(uow, from_=first.next_from.as_text())

    assert first.next_from.backwards is True
    assert second.events[0].event.starts_at < first.events[-1].event.starts_at


async def test_the_page_starts_at_the_instant_it_was_asked_for() -> None:
    uow = FakeEventsUnitOfWork(planned("one", "two", "three"), communities=a_community())

    page = await read(uow, from_=str(NOW + timedelta(hours=2)))

    assert [details.event.title for details in page.events] == ["two", "three"]


async def test_a_marker_no_page_ever_handed_out_is_refused() -> None:
    uow = FakeEventsUnitOfWork(planned("one"), communities=a_community())

    with pytest.raises(UnknownPageError):
        await read(uow, from_="2026-03-04T18:00:00Z~not-the-row-it-stopped-on")


async def test_a_community_that_does_not_exist_says_so() -> None:
    """An empty list would be the answer a typo deserves least."""
    uow = FakeEventsUnitOfWork(planned("one"), communities=a_community(BOOK_CLUB))

    with pytest.raises(CommunityNotFoundError):
        await read(uow, community_id=uuid4())


async def test_reading_a_communitys_list_writes_nothing_down() -> None:
    uow = FakeEventsUnitOfWork(planned("one"), communities=a_community())

    await reading(uow)

    assert uow.committed is False
