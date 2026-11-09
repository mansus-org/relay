"""One page of what a community has on: its own list, from wherever the reader asked to start."""

from uuid import UUID

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
from relay.contexts.events.domain.cells import DEFAULT_RADIUS_KM
from relay.contexts.events.domain.community import CommunityNotFoundError
from relay.contexts.events.domain.listing import (
    EventDetails,
    EventListingPage,
    ListingStart,
    marker_after,
)
from relay.contexts.events.domain.ports import CellNeighbourhood
from relay.shared.application import Clock


class GetCommunityEvents:
    """Reads one community's events a page at a time, in the direction `from` asked for.

    Two filters, and they do different jobs. The community says whose list this is. The
    ring says what the reader is allowed to see, and it applies here the same way it
    applies everywhere else: being a member is what lets you put an event on this list,
    never what lets you read one, so a plan your community filed an hour away is not on
    your page. Reading the list is public the way every read of an event is public.
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
        self,
        *,
        community_id: UUID,
        cell: str,
        radius_km: float = DEFAULT_RADIUS_KM,
        from_: str | None = None,
    ) -> EventListingPage:
        cells = self._neighbourhood.visible_from(cell, radius_km)
        start = ListingStart.read(from_, now=self._clock.now())
        async with self._uow:
            found = await self._uow.events.page_for_community(
                community_id=community_id, cells=cells, start=start, limit=self.PAGE_SIZE + 1
            )
            # One extra read tells us whether there is more without a second query.
            more = len(found) > self.PAGE_SIZE
            events = found[: self.PAGE_SIZE]
            counts = await self._uow.rsvps.counts_for([event.id for event in events])
            # The one read that says whether this community is a thing at all, because an
            # empty list is exactly what a community with nothing on looks like and only
            # this tells the two apart.
            names = await self._uow.communities.names_for([community_id])
        name = names.get(community_id)
        if name is None:
            raise CommunityNotFoundError(f"No community {community_id} to show events for.")
        return EventListingPage(
            events=tuple(
                EventDetails(event=event, rsvp_count=counts.get(event.id, 0), community_name=name)
                for event in events
            ),
            # The marker is the last row read, not the last instant: see ListingStart.
            next_from=marker_after(events, start) if more and events else None,
        )
