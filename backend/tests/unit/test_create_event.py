"""Planning an event: it gets written down, or nothing does."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from relay.contexts.events.application import CreateEvent
from relay.contexts.events.domain.cells import UnknownCellError
from relay.contexts.events.domain.community import CommunityNotFoundError, NotAMemberError
from relay.contexts.events.domain.event import InvalidTimeError
from relay.contexts.events.domain.listing import ListingStart
from relay.shared.domain import ValidationError
from tests.fakes.clock import FixedClock
from tests.fakes.events import FakeEventsUnitOfWork, FixedCells, InMemoryCommunities

#: When the event was planned, and when it happens: the two must never be confused.
PLANNED_AT = datetime(2026, 3, 1, 9, 30, tzinfo=UTC)
STARTS = datetime(2026, 3, 4, 18, tzinfo=UTC)
#: The host these tests plan as, so a membership can be about somebody.
HOST = UUID("11111111-1111-1111-1111-111111111111")


def planning(uow: FakeEventsUnitOfWork) -> CreateEvent:
    return CreateEvent(uow=uow, clock=FixedClock(PLANNED_AT), cells=FixedCells())


async def test_an_event_is_written_down_with_the_time_it_was_planned() -> None:
    uow = FakeEventsUnitOfWork()
    host = uuid4()

    event = await planning(uow).execute(
        host_id=host, title="Book swap", starts_at=STARTS, location_cell="here"
    )

    assert uow.committed is True
    assert await uow.events.get(event.id) is not None
    assert event.host_id == host
    assert event.created_at == PLANNED_AT
    assert event.starts_at == STARTS
    assert event.location_cell == "here"


async def test_an_event_can_be_planned_without_a_place_and_without_an_end() -> None:
    """A plan whose place is not settled yet is still a plan; it just reaches no locality."""
    uow = FakeEventsUnitOfWork()

    event = await planning(uow).execute(host_id=uuid4(), title="Book swap", starts_at=STARTS)

    assert event.location_cell is None
    assert event.ends_at is None
    assert event.details is None
    assert uow.committed is True


async def test_an_event_is_filed_under_the_cell_it_was_given() -> None:
    """The cell is kept as the cell standard returns it, which is how a list reads it back."""
    uow = FakeEventsUnitOfWork()

    event = await planning(uow).execute(
        host_id=uuid4(), title="Book swap", starts_at=STARTS, location_cell="here"
    )

    assert event.location_cell == "here"
    assert await uow.events.page_listing(
        cells=["here"], start=ListingStart(at=PLANNED_AT), limit=20
    ) == [event]


async def test_a_locality_left_blank_is_no_locality_rather_than_a_cell_of_its_own() -> None:
    uow = FakeEventsUnitOfWork()

    event = await planning(uow).execute(
        host_id=uuid4(), title="Book swap", starts_at=STARTS, location_cell="   "
    )

    assert event.location_cell is None


async def test_an_event_filed_where_no_locality_ever_looks_is_not_written_down() -> None:
    """Better a refusal than a 201 for an event its host will never see again."""
    uow = FakeEventsUnitOfWork()

    with pytest.raises(UnknownCellError):
        await planning(uow).execute(
            host_id=uuid4(), title="Book swap", starts_at=STARTS, location_cell="99"
        )

    assert uow.committed is False
    assert (
        await uow.events.page_listing(cells=["here"], start=ListingStart(at=PLANNED_AT), limit=20)
        == []
    )


async def test_nothing_is_written_down_when_an_event_was_never_planned() -> None:
    uow = FakeEventsUnitOfWork()

    with pytest.raises(ValidationError, match="needs a title"):
        await planning(uow).execute(host_id=uuid4(), title="   ", starts_at=STARTS)

    assert uow.committed is False
    assert (
        await uow.events.page_listing(cells=["here"], start=ListingStart(at=PLANNED_AT), limit=20)
        == []
    )


async def test_an_event_that_ends_before_it_starts_is_not_written_down() -> None:
    uow = FakeEventsUnitOfWork()

    with pytest.raises(ValidationError, match="end"):
        await planning(uow).execute(
            host_id=uuid4(),
            title="Book swap",
            starts_at=STARTS,
            ends_at=datetime(2026, 3, 4, 17, tzinfo=UTC),
        )

    assert uow.committed is False


async def test_an_end_cleared_in_a_form_is_kept_as_no_end() -> None:
    """`ends_at` emptied in a form is a field cleared, not a time that says nothing.

    The same answer as a place left blank: the host does not know when it finishes, so
    the event goes on for as long as it goes on rather than being refused over a space.
    """
    uow = FakeEventsUnitOfWork()

    event = await planning(uow).execute(
        host_id=uuid4(), title="Book swap", starts_at=STARTS, ends_at="   "
    )

    assert event.ends_at is None
    assert uow.committed is True


async def test_an_end_that_is_not_a_time_at_all_is_refused() -> None:
    """Words where the end time goes are the host's mistake to hear about, not a silent maybe."""
    uow = FakeEventsUnitOfWork()

    with pytest.raises(InvalidTimeError):
        await planning(uow).execute(
            host_id=uuid4(), title="Book swap", starts_at=STARTS, ends_at="after the rain"
        )

    assert uow.committed is False


# Filing an event under a community.

COMMUNITY = UUID("33333333-3333-3333-3333-333333333333")
STRANGER = UUID("44444444-4444-4444-4444-444444444444")


def a_community(*members: UUID) -> InMemoryCommunities:
    """The community these tests file under, with whoever it says belongs to it."""
    found = InMemoryCommunities()
    found.found(COMMUNITY, "Vigo Book Club", *members)
    return found


async def test_an_event_can_be_filed_under_a_community_its_host_belongs_to() -> None:
    uow = FakeEventsUnitOfWork(communities=a_community(HOST))

    event = await planning(uow).execute(
        host_id=HOST, title="Book swap", starts_at=STARTS, community_id=COMMUNITY
    )

    assert uow.committed is True
    assert event.community_id == COMMUNITY


async def test_an_event_filed_under_a_community_is_still_written_once() -> None:
    """The community is a column on the event, not a second row anywhere.

    It is worth saying out loud, because the tempting wrong shape is a join table: an
    event belongs to one community, and a second one is a second event.
    """
    uow = FakeEventsUnitOfWork(communities=a_community(HOST))

    event = await planning(uow).execute(
        host_id=HOST, title="Book swap", starts_at=STARTS, community_id=COMMUNITY
    )

    listed = await uow.events.page_for_community(
        community_id=COMMUNITY, start=ListingStart(at=PLANNED_AT), limit=10
    )
    assert [written.id for written in listed] == [event.id]


async def test_a_stranger_cannot_file_an_event_under_a_community() -> None:
    """Whatever else a stranger may plan, they cannot put it on a group's list."""
    uow = FakeEventsUnitOfWork(communities=a_community(HOST))

    with pytest.raises(NotAMemberError):
        await planning(uow).execute(
            host_id=STRANGER, title="Book swap", starts_at=STARTS, community_id=COMMUNITY
        )

    assert uow.committed is False
    listed = await uow.events.page_for_community(
        community_id=COMMUNITY, start=ListingStart(at=PLANNED_AT), limit=10
    )
    assert listed == []


async def test_a_community_that_does_not_exist_is_said_so_rather_than_refused_as_not_a_member() -> (
    None
):
    """Two mistakes, two messages: a copied-and-torn-off id is not the same as being out of it."""
    uow = FakeEventsUnitOfWork(communities=a_community(HOST))

    with pytest.raises(CommunityNotFoundError):
        await planning(uow).execute(
            host_id=HOST, title="Book swap", starts_at=STARTS, community_id=uuid4()
        )

    assert uow.committed is False


async def test_planning_without_a_community_never_asks_who_is_in_what() -> None:
    """The common case stays the cheap case: no community named, no membership looked up."""
    uow = FakeEventsUnitOfWork()

    event = await planning(uow).execute(host_id=HOST, title="Book swap", starts_at=STARTS)

    assert event.community_id is None
    assert uow.committed is True
