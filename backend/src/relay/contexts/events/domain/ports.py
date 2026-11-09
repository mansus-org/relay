"""Ports the events context needs; infrastructure supplies the implementations."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from uuid import UUID

from relay.contexts.events.domain.event import Event
from relay.contexts.events.domain.listing import ListingStart
from relay.contexts.events.domain.rsvp import Rsvp
from relay.shared.domain import Repository


class EventRepository(Repository[Event, UUID]):
    """Events by id, and the next ones on in a neighbourhood."""

    @abstractmethod
    async def page_listing(
        self, *, cells: Iterable[str], start: ListingStart, limit: int
    ) -> list[Event]:
        """The page that starts at `start`, in the order `start` reads in.

        Forwards that is soonest first from the marker, backwards most recent first
        before it; either way the marker names one row rather than one minute, so
        nothing sits between two pages unseen. An event with no `location_cell` is in
        none of the cells, so it never comes back.
        """

    @abstractmethod
    async def page_for_community(
        self, *, community_id: UUID, start: ListingStart, limit: int
    ) -> list[Event]:
        """The same pages, read out of one community instead of one neighbourhood.

        A community is people rather than a place, so nothing here is cut by cells: an
        event filed under it is on its list whether or not anyone has said where it
        happens, and an event filed under it *and* at a cell is on both lists.
        """


class RsvpRepository(Repository[Rsvp, UUID]):
    """Who is going to what."""

    @abstractmethod
    async def by_member(self, *, event_id: UUID, member_id: UUID) -> Rsvp | None:
        """This member's place at this event, if they have taken one."""

    @abstractmethod
    async def delete(self, rsvp: Rsvp) -> None:
        """Give up a place. The caller has already found it."""

    @abstractmethod
    async def count_for(self, event_id: UUID) -> int:
        """How many are going to this one."""

    @abstractmethod
    async def counts_for(self, event_ids: Sequence[UUID]) -> dict[UUID, int]:
        """How many are going to each of these, in one read.

        An event nobody is going to has no entry, and the caller reads that as none.
        """


class Communities(ABC):
    """The read side of the communities context, as far as events is allowed to see it.

    Read-only, and the only way this context learns anything about a community: the
    communities context keeps its name, its members and its reach to itself.
    """

    @abstractmethod
    async def names_for(self, community_ids: Iterable[UUID]) -> dict[UUID, str]:
        """The name of each of these, in one read.

        An id with no name beside it is an id no community owns, which is how a caller
        tells a community that was never there from one that is simply empty.
        """

    @abstractmethod
    async def is_member(self, *, community_id: UUID, member_id: UUID) -> bool:
        """Whether this person is one of the people who make up this community.

        False for a community that does not exist, and the caller decides whether that
        deserves a different message from one it does.
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
