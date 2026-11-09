"""One page of what is on: the next events in a locality, soonest first."""

from datetime import datetime

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
from relay.contexts.events.domain.cells import DEFAULT_RADIUS_KM
from relay.contexts.events.domain.event import instant
from relay.contexts.events.domain.listing import EventDetails, EventListingPage
from relay.contexts.events.domain.ports import CellNeighbourhood
from relay.shared.application import Clock

#: The one word in `from` that means "stop filtering by time". Everything else in
#: `from` is a date, and a date is a wall.
ALL_PAST = "past"


def reading_from(value: str | None, *, now: datetime) -> datetime | None:
    """Where `from` starts reading, or None when it does not start anywhere.

    No `from` is the default wall: now. A date (`2026-03-04`) is that midnight in UTC
    and a full timestamp is itself, so the same word pages forward from the last row of
    the page before it. `past` is the way to ask for what already happened, which the
    default refuses.
    """
    if value is None:
        return now
    if value.strip().lower() == ALL_PAST:
        return None
    return instant(value)


class GetEvents:
    """Reads a neighbourhood's events soonest first, a page at a time.

    The locality filter is the cell and the radius and nothing else: an event planned
    outside the ring, or with no cell at all, is not in this list. The time filter is
    `from`, and its default is now — a list of what is on is a list of what is still to
    come, and what has already started is only here when the reader asks for it.
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
        after = reading_from(from_, now=self._clock.now())
        async with self._uow:
            found = await self._uow.events.page_upcoming(
                cells=cells, after=after, limit=self.PAGE_SIZE + 1
            )
            # One extra read tells us whether there is more without a second query.
            more = len(found) > self.PAGE_SIZE
            events = found[: self.PAGE_SIZE]
            counts = await self._uow.rsvps.counts_for([event.id for event in events])
        return EventListingPage(
            events=tuple(
                EventDetails(event=event, rsvp_count=counts.get(event.id, 0)) for event in events
            ),
            next_from=events[-1].starts_at if more and events else None,
        )
