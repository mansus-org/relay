"""In-memory stand-ins for the events ports, so a use-case test never touches a database."""

from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
from relay.contexts.events.domain.cells import UnknownCellError
from relay.contexts.events.domain.event import Event
from relay.contexts.events.domain.listing import ListingStart
from relay.contexts.events.domain.ports import (
    CellNeighbourhood,
    CellStandard,
    Communities,
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
    community_id: UUID | None = None,
) -> Event:
    """An event a test can name in one line."""
    return Event.plan(
        host_id=host_id or uuid4(),
        title=title,
        starts_at=starts_at,
        created_at=planned_at,
        location_cell=cell,
        community_id=community_id,
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

    async def page_listing(
        self, *, cells: Iterable[str], start: ListingStart, limit: int
    ) -> list[Event]:
        """The same cut the table makes: at a row, not at an instant.

        A page that stops in the middle of a minute has to resume in the middle of that
        minute, so the fake compares the pair the repository does rather than the time
        alone. Only a marker is strict; a wall with no row named yet puts whatever starts
        exactly at it on the forwards page, not the backwards one.
        """
        wanted = set(cells)
        return self._page(lambda event: event.location_cell in wanted, start, limit)

    async def page_for_community(
        self, *, community_id: UUID, cells: Iterable[str], start: ListingStart, limit: int
    ) -> list[Event]:
        """The same two cuts the table makes: whose list it is, and the reader's ring."""
        wanted = set(cells)
        return self._page(
            lambda event: event.community_id == community_id and event.location_cell in wanted,
            start,
            limit,
        )

    def _page(
        self, belongs: Callable[[Event], bool], start: ListingStart, limit: int
    ) -> list[Event]:
        seen_id = start.seen_id

        def on_this_page(event: Event) -> bool:
            if seen_id is None:
                # No row named yet, so the instant alone cuts it, and the event at the
                # wall belongs on the page going forwards from there.
                if start.backwards:
                    return event.starts_at < start.at
                return event.starts_at >= start.at
            wall = (start.at, seen_id)
            seen = (event.starts_at, event.id)
            return seen < wall if start.backwards else seen > wall

        found = [event for event in self._items.values() if belongs(event) and on_this_page(event)]
        found.sort(key=lambda event: (event.starts_at, event.id), reverse=start.backwards)
        return found[:limit]


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

    async def delete(self, rsvp: Rsvp) -> None:
        self._items.pop(rsvp.id, None)

    async def count_for(self, event_id: UUID) -> int:
        return sum(1 for rsvp in self._items.values() if rsvp.event_id == event_id)

    async def counts_for(self, event_ids: Sequence[UUID]) -> dict[UUID, int]:
        return {event_id: await self.count_for(event_id) for event_id in event_ids}


class InMemoryCommunities(Communities):
    """The communities a test named, and who it said is in them.

    Membership is a set the test fills, because the rule the use case cares about is
    "is this person in it", and no fake needs to model how they got there.
    """

    def __init__(
        self, names: dict[UUID, str] | None = None, members: dict[UUID, set[UUID]] | None = None
    ) -> None:
        self.names = names or {}
        self.members = members or {}

    def found(self, community_id: UUID, name: str, *members: UUID) -> None:
        """A community exists, with whoever is in it."""
        self.names[community_id] = name
        self.members.setdefault(community_id, set()).update(members)

    async def names_for(self, community_ids: Iterable[UUID]) -> dict[UUID, str]:
        return {cid: self.names[cid] for cid in community_ids if cid in self.names}

    async def is_member(self, *, community_id: UUID, member_id: UUID) -> bool:
        return member_id in self.members.get(community_id, set())


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

    def __init__(
        self,
        events: Iterable[Event] = (),
        rsvps: Iterable[Rsvp] = (),
        communities: InMemoryCommunities | None = None,
    ) -> None:
        super().__init__()
        self.events = InMemoryEventRepository(events)
        self.rsvps = InMemoryRsvpRepository(rsvps)
        self.communities = communities or InMemoryCommunities()
