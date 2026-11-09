"""One page of what is on: a locality's events, from wherever the reader asked to start."""

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
from relay.contexts.events.domain.cells import DEFAULT_RADIUS_KM
from relay.contexts.events.domain.listing import (
    EventDetails,
    EventListingPage,
    ListingStart,
    marker_after,
)
from relay.contexts.events.domain.ports import CellNeighbourhood
from relay.shared.application import Clock


class GetEvents:
    """Reads a neighbourhood's events a page at a time, in the direction `from` asked for.

    The locality filter is the cell and the radius and nothing else: an event planned
    outside the ring, or with no cell at all, is not in this list. The time filter is
    `from`, and its default is now — a list of what is on is a list of what is still to
    come, and what has already started is only here when the reader asks for it. An event
    filed under a community is here too, when its cell is in the ring: filing it under a
    community says who it is for, not where it belongs.
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
        self, *, cell: str, radius_km: float = DEFAULT_RADIUS_KM, from_: str | None = None
    ) -> EventListingPage:
        cells = self._neighbourhood.visible_from(cell, radius_km)
        start = ListingStart.read(from_, now=self._clock.now())
        async with self._uow:
            found = await self._uow.events.page_listing(
                cells=cells, start=start, limit=self.PAGE_SIZE + 1
            )
            # One extra read tells us whether there is more without a second query.
            more = len(found) > self.PAGE_SIZE
            events = found[: self.PAGE_SIZE]
            counts = await self._uow.rsvps.counts_for([event.id for event in events])
            # One read for the whole page, the same way the tallies are counted: a page
            # of events is not about to become a page and a half of queries.
            names = await self._uow.communities.names_for(
                {event.community_id for event in events if event.community_id is not None}
            )
        return EventListingPage(
            events=tuple(
                EventDetails(
                    event=event,
                    rsvp_count=counts.get(event.id, 0),
                    community_name=(names.get(event.community_id) if event.community_id else None),
                )
                for event in events
            ),
            # The marker is the last row read, not the last instant: see ListingStart.
            next_from=marker_after(events, start) if more and events else None,
        )
