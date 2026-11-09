"""Ports the events context needs; infrastructure supplies the implementations."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from datetime import datetime
from uuid import UUID

from relay.contexts.events.domain.event import Event
from relay.contexts.events.domain.rsvp import Rsvp
from relay.shared.domain import Repository


class EventRepository(Repository[Event, UUID]):
    """Events by id, and the next ones on in a neighbourhood."""

    @abstractmethod
    async def page_upcoming(
        self, *, cells: Iterable[str], after: datetime, limit: int
    ) -> list[Event]:
        """Soonest first: events in one of `cells` starting later than `after`.

        An event with no `location_cell` is in none of the cells, so it never comes
        back. An event that has already started is not here either: this is what is
        still to come.
        """


class RsvpRepository(Repository[Rsvp, UUID]):
    """Who is going to what."""

    @abstractmethod
    async def by_member(self, *, event_id: UUID, member_id: UUID) -> Rsvp | None:
        """This member's place at this event, if they have taken one."""

    @abstractmethod
    async def count_for(self, event_id: UUID) -> int:
        """How many are going to this one."""

    @abstractmethod
    async def counts_for(self, event_ids: Sequence[UUID]) -> dict[UUID, int]:
        """How many are going to each of these, in one read.

        An event nobody is going to has no entry, and the caller reads that as none.
        """


class CellNeighbourhood(ABC):
    """The cells a reader standing in `cell` can see events from, `radius_km` out."""

    @abstractmethod
    def visible_from(self, cell: str, radius_km: float) -> set[str]: ...


class CellStandard(ABC):
    """Which strings count as a cell here, and the one way a cell is written."""

    @abstractmethod
    def normalise(self, cell: str) -> str:
        """The form of `cell` that a list of events will read back.

        Raises UnknownCellError for anything it would never read: a string that is not
        a cell, or one at a resolution no list is served at. Saving either would hand
        the host an event no locality can ever show.
        """
