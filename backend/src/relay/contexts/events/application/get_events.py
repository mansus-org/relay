"""One page of what is on: the next events in a locality, soonest first."""

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
from relay.contexts.events.domain.cells import DEFAULT_RADIUS_KM
from relay.contexts.events.domain.event import instant
from relay.contexts.events.domain.listing import EventDetails, EventListingPage
from relay.contexts.events.domain.ports import CellNeighbourhood
from relay.shared.application import Clock


class GetEvents:
    """Reads a neighbourhood's next events, soonest first, a page at a time.

    The locality filter is the cell and the radius and nothing else: an event planned
    outside the ring, or with no cell at all, is not in this list. Neither is one that
    has already started — a list of what is on is a list of what is still to come, and
    `after` is how you walk forward past it.
    """

    #: How many to hand back at once. The same page a person scrolls through.
    PAGE_SIZE = 20

    def __init__(
        self, uow: EventsUnitOfWork, neighbourhood: CellNeighbourhood, clock: Clock
    ) -> None:
        self._uow = uow
        self._neighbourhood = neighbourhood
        self._clock = clock

    async def execute(
        self, *, cell: str, radius_km: float = DEFAULT_RADIUS_KM, after: str | None = None
    ) -> EventListingPage:
        cells = self._neighbourhood.visible_from(cell, radius_km)
        since = instant(after) if after is not None else self._clock.now()
        async with self._uow:
            found = await self._uow.events.page_upcoming(
                cells=cells, after=since, limit=self.PAGE_SIZE + 1
            )
            # One extra read tells us whether there is more without a second query.
            more = len(found) > self.PAGE_SIZE
            events = found[: self.PAGE_SIZE]
            counts = await self._uow.rsvps.counts_for([event.id for event in events])
        return EventListingPage(
            events=tuple(
                EventDetails(event=event, rsvp_count=counts.get(event.id, 0)) for event in events
            ),
            next_after=events[-1].starts_at if more and events else None,
        )
