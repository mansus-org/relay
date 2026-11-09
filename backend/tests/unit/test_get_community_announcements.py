"""A community's announcements: what it lately filed, newest filed first, in reach."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from relay.contexts.events.application import GetCommunityAnnouncements
from relay.contexts.events.domain.community import CommunityNotFoundError
from relay.contexts.events.domain.event import Event
from tests.fakes.events import (
    FakeEventsUnitOfWork,
    FixedNeighbourhood,
    InMemoryCommunities,
    an_event,
    going_to,
)

NOW = datetime(2026, 3, 4, 12, tzinfo=UTC)
# The reader stands in "here"; "far" is a cell nobody nearby can see. The same ring as
# every other list — a plan an hour away is not an announcement to the hour-away member.
NEIGHBOURHOOD = FixedNeighbourhood({"here": {"here"}, "far": {"far"}})
BOOK_CLUB = UUID("11111111-1111-1111-1111-111111111111")
CHOIR = UUID("22222222-2222-2222-2222-222222222222")


def a_community(*ids: UUID) -> InMemoryCommunities:
    """The communities these tests name; reading a feed asks about membership nowhere else."""
    found = InMemoryCommunities()
    for community_id in ids or (BOOK_CLUB,):
        found.found(community_id, f"The {community_id.hex[:8]}")
    return found


def filed(*titles: str, community_id: UUID = BOOK_CLUB, cell: str | None = "here") -> list[Event]:
    """Events filed under one community, in the order they were filed, an hour apart."""
    return [
        an_event(
            title,
            community_id=community_id,
            cell=cell,
            planned_at=NOW + timedelta(hours=index),
        )
        for index, title in enumerate(titles)
    ]


async def read(uow: FakeEventsUnitOfWork, community_id: UUID = BOOK_CLUB):
    use_case = GetCommunityAnnouncements(uow=uow, neighbourhood=NEIGHBOURHOOD)
    return await use_case.execute(community_id=community_id, cell="here")


async def test_the_newest_filing_is_first_and_not_the_next_one() -> None:
    """A feed is what a community has lately said, so it reads the clock it was written on.

    "tonight" was put up first and happens first; "next month" was put up second and
    happens a month out. The calendar would lead with "tonight"; the feed leads with what
    the community last said, which is the thing that is actually new in a feed of posts.
    """
    uow = FakeEventsUnitOfWork(
        [
            an_event(
                "tonight",
                community_id=BOOK_CLUB,
                starts_at=NOW + timedelta(hours=2),
                planned_at=NOW,
            ),
            an_event(
                "next month",
                community_id=BOOK_CLUB,
                starts_at=NOW + timedelta(days=30),
                planned_at=NOW + timedelta(hours=1),
            ),
        ],
        communities=a_community(),
    )

    assert [details.event.title for details in await read(uow)] == ["next month", "tonight"]


async def test_an_event_that_has_already_happened_is_still_being_announced() -> None:
    """It stays on the feed until something newer pushes it off, and not until then.

    The calendar drops what has started because the calendar is about what is coming. A
    feed has no such wall: last week's reading is still the newest thing this community
    said, and pretending otherwise would leave a quiet community with an empty feed.
    """
    uow = FakeEventsUnitOfWork(
        [
            an_event(
                "last week",
                community_id=BOOK_CLUB,
                starts_at=NOW - timedelta(days=7),
                planned_at=NOW - timedelta(days=8),
            ),
            an_event(
                "yesterday",
                community_id=BOOK_CLUB,
                starts_at=NOW - timedelta(days=1),
                planned_at=NOW - timedelta(days=2),
            ),
        ],
        communities=a_community(),
    )

    assert [details.event.title for details in await read(uow)] == ["yesterday", "last week"]


async def test_another_communitys_event_is_not_announced_here() -> None:
    uow = FakeEventsUnitOfWork(
        [*filed("ours"), *filed("theirs", community_id=CHOIR)],
        communities=a_community(BOOK_CLUB, CHOIR),
    )

    assert [details.event.title for details in await read(uow)] == ["ours"]


async def test_an_event_that_belongs_to_no_community_is_announced_by_nobody() -> None:
    uow = FakeEventsUnitOfWork(
        [*filed("ours"), an_event("just a place", community_id=None)],
        communities=a_community(),
    )

    assert [details.event.title for details in await read(uow)] == ["ours"]


async def test_the_ring_applies_here_the_way_it_does_everywhere() -> None:
    """The same two cuts as the calendar's, for the same two reasons.

    Membership is what lets a member file a plan, never what lets them see one, so the
    plan filed in another town is not announced to this one; and a plan that has no place
    yet is in nobody's reach, so it is announced to nobody either.
    """
    uow = FakeEventsUnitOfWork(
        [
            *filed("in the hall"),
            an_event("no venue yet", community_id=BOOK_CLUB, cell=None),
            an_event("somewhere else", community_id=BOOK_CLUB, cell="far"),
        ],
        communities=a_community(),
    )

    assert [details.event.title for details in await read(uow)] == ["in the hall"]


async def test_a_feed_is_a_glance_and_not_the_whole_calendar() -> None:
    """Past a handful, the calendar is the surface that pages; the feed just stops."""
    uow = FakeEventsUnitOfWork(
        [
            an_event(
                f"event {index}",
                community_id=BOOK_CLUB,
                planned_at=NOW + timedelta(hours=index),
            )
            for index in range(14)
        ],
        communities=a_community(),
    )

    found = await read(uow)

    assert len(found) == 10
    assert found[0].event.title == "event 13"


async def test_every_announcement_carries_how_many_are_going_and_who_announced_it() -> None:
    booked = an_event("Book swap", community_id=BOOK_CLUB)
    uow = FakeEventsUnitOfWork(
        [booked, *filed("Silent reading")],
        rsvps=[going_to(booked, uuid4()), going_to(booked, uuid4())],
        communities=a_community(),
    )

    found = await read(uow)

    assert [(details.event.title, details.rsvp_count) for details in found] == [
        ("Silent reading", 0),
        ("Book swap", 2),
    ]
    assert all(details.community_name == "The 11111111" for details in found)


async def test_a_community_that_does_not_exist_says_so() -> None:
    """Borrowed as a door, this cannot answer for a community that never was."""
    uow = FakeEventsUnitOfWork(filed("one"), communities=a_community(BOOK_CLUB))

    with pytest.raises(CommunityNotFoundError):
        await read(uow, community_id=uuid4())


async def test_reading_a_communitys_announcements_writes_nothing_down() -> None:
    uow = FakeEventsUnitOfWork(filed("one"), communities=a_community())

    await read(uow)

    assert uow.committed is False
