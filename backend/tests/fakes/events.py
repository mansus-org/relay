"""In-memory stand-ins for the events ports, so a use-case test never touches a database."""

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
from relay.contexts.events.domain.cells import UnknownCellError
from relay.contexts.events.domain.event import Event
from relay.contexts.events.domain.ports import (
    CellNeighbourhood,
    CellStandard,
    EventRepository,
    RsvpRepository,
)
from relay.contexts.events.domain.rsvp import AlreadyRsvpedError, Rsvp
from tests.fakes.repository import InMemoryRepository
from tests.fakes.unit_of_work import FakeUnitOfWork

#: When a test's event was planned, and when it starts: two days apart, so a test can
#: tell the time it was written down from the time it happens.
PLANNED = datetime(2026, 3, 1, tzinfo=UTC)
STARTS = datetime(2026, 3, 4, 18, tzinfo=UTC)


def an_event(
    title: str = "Neighbourhood clean-up",
    *,
    cell: str | None = "here",
    starts_at: datetime = STARTS,
    host_id: UUID | None = None,
    planned_at: datetime = PLANNED,
) -> Event:
    """An event a test can name in one line."""
    return Event.plan(
        host_id=host_id or uuid4(),
        title=title,
        starts_at=starts_at,
        created_at=planned_at,
        location_cell=cell,
    )


def going_to(event: Event, member_id: UUID | None = None, *, at: datetime = PLANNED) -> Rsvp:
    """A place already taken at an event."""
    return Rsvp.go(event_id=event.id, member_id=member_id or uuid4(), at=at)


class InMemoryEventRepository(InMemoryRepository[Event], EventRepository):
    """The events in a dict, and the listing query done in Python."""

    def __init__(self, events: Iterable[Event] = ()) -> None:
        super().__init__()
        for event in events:
            self._items[event.id] = event

    async def page_upcoming(
        self, *, cells: Iterable[str], after: datetime, limit: int
    ) -> list[Event]:
        wanted = set(cells)
        upcoming = [
            event
            for event in self._items.values()
            if event.location_cell in wanted and event.starts_at > after
        ]
        upcoming.sort(key=lambda event: event.starts_at)
        return upcoming[:limit]


class InMemoryRsvpRepository(InMemoryRepository[Rsvp], RsvpRepository):
    """Who is going, in a dict, with the same one-place-per-member rule as the table."""

    def __init__(self, rsvps: Iterable[Rsvp] = ()) -> None:
        super().__init__()
        for rsvp in rsvps:
            self._items[rsvp.id] = rsvp

    async def add(self, entity: Rsvp) -> None:
        """The unique pair, enforced here so a test can see the race being absorbed."""
        taken = await self.by_member(event_id=entity.event_id, member_id=entity.member_id)
        if taken is not None:
            raise AlreadyRsvpedError(f"{entity.member_id} is already going to {entity.event_id}.")
        await super().add(entity)

    async def by_member(self, *, event_id: UUID, member_id: UUID) -> Rsvp | None:
        return next(
            (
                rsvp
                for rsvp in self._items.values()
                if rsvp.event_id == event_id and rsvp.member_id == member_id
            ),
            None,
        )

    async def count_for(self, event_id: UUID) -> int:
        return sum(1 for rsvp in self._items.values() if rsvp.event_id == event_id)

    async def counts_for(self, event_ids: Sequence[UUID]) -> dict[UUID, int]:
        return {event_id: await self.count_for(event_id) for event_id in event_ids}


class FixedNeighbourhood(CellNeighbourhood):
    """A neighbourhood a test hands the rings itself, so no test depends on H3."""

    def __init__(self, rings: dict[str, set[str]] | None = None) -> None:
        self._rings = rings or {}

    def visible_from(self, cell: str, radius_km: float) -> set[str]:
        return self._rings.get(cell, {cell})


class FixedCells(CellStandard):
    """A cell standard that knows the cells a test named, and refuses every other string."""

    def __init__(self, known: Iterable[str] = ("here",)) -> None:
        self._known = set(known)

    def normalise(self, cell: str) -> str:
        if cell not in self._known:
            raise UnknownCellError(f"{cell!r} is not a cell here.")
        return cell


class FakeEventsUnitOfWork(FakeUnitOfWork, EventsUnitOfWork):
    """A transaction whose events and places are the ones a test passed in."""

    def __init__(self, events: Iterable[Event] = (), rsvps: Iterable[Rsvp] = ()) -> None:
        super().__init__()
        self.events = InMemoryEventRepository(events)
        self.rsvps = InMemoryRsvpRepository(rsvps)
