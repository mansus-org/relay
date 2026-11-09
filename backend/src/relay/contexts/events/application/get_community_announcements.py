"""What a community has lately filed, newest filed first, to sit beside its posts."""

from uuid import UUID

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
from relay.contexts.events.domain.cells import DEFAULT_RADIUS_KM
from relay.contexts.events.domain.community import CommunityNotFoundError
from relay.contexts.events.domain.listing import EventDetails
from relay.contexts.events.domain.ports import CellNeighbourhood


class GetCommunityAnnouncements:
    """The handful of events a community has most recently put up, for its feed.

    The calendar list answers "what is coming off, and when"; this answers "what has this
    community said lately", which is the question a feed of its posts is asked next to its
    posts. So the order is by when a plan was filed and not by when it happens, and a plan
    that has already happened stays on the feed until something newer pushes it off.

    The ring is not relaxed here either: a plan nobody can reach is not worth announcing to
    them, so a reader with no cell to stand on is handed nothing. Membership is not asked
    about, because reading an event is public everywhere else — whoever is allowed to read
    the feed at all is the caller's business, and the community's own feed route settles
    it before it asks this.
    """

    #: How many to put on a feed. A feed is a glance and not a scroll: past this, the
    #: calendar is the surface that pages.
    LIMIT = 10

    def __init__(self, uow: EventsUnitOfWork, neighbourhood: CellNeighbourhood) -> None:
        self._uow = uow
        self._neighbourhood = neighbourhood

    async def execute(
        self,
        *,
        community_id: UUID,
        cell: str,
        radius_km: float | None = None,
    ) -> tuple[EventDetails, ...]:
        """The community's newest filings, in the reader's reach, newest filed first."""
        reach = DEFAULT_RADIUS_KM if radius_km is None else radius_km
        cells = self._neighbourhood.visible_from(cell, reach)
        async with self._uow:
            found = await self._uow.events.recent_for_community(
                community_id=community_id, cells=cells, limit=self.LIMIT
            )
            counts = await self._uow.rsvps.counts_for([event.id for event in found])
            # The one read that says whether this community is a thing at all, so that a
            # borrowed door cannot answer for a community that never existed.
            names = await self._uow.communities.names_for([community_id])
        name = names.get(community_id)
        if name is None:
            raise CommunityNotFoundError(f"No community {community_id} to announce for.")
        return tuple(
            EventDetails(event=event, rsvp_count=counts.get(event.id, 0), community_name=name)
            for event in found
        )
