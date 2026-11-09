"""One page of what a community has on: its own list, from wherever the reader asked to start."""

from uuid import UUID

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
from relay.contexts.events.domain.community import CommunityNotFoundError
from relay.contexts.events.domain.listing import (
    EventDetails,
    EventListingPage,
    ListingStart,
    marker_after,
)
from relay.shared.application import Clock


class GetCommunityEvents:
    """Reads one community's events a page at a time, in the direction `from` asked for.

    The filter is the community and nothing else. A community is people rather than a
    place, so its list is not cut by a ring the way a locality's is: whatever was filed
    under it is on it, including the plans whose place nobody has settled yet. Reading it
    is public the way every read of an event is public — being a member is what lets you
    put something on the list, not what lets you read it.
    """

    #: How many to hand back at once. The same page a person scrolls through.
    PAGE_SIZE = 20

    def __init__(self, uow: EventsUnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, *, community_id: UUID, from_: str | None = None) -> EventListingPage:
        start = ListingStart.read(from_, now=self._clock.now())
        async with self._uow:
            found = await self._uow.events.page_for_community(
                community_id=community_id, start=start, limit=self.PAGE_SIZE + 1
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
