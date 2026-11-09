"""What is on: a page of upcoming events, and how many people are going to each."""

from datetime import UTC, datetime

from relay.contexts.events.domain.event import Event
from relay.shared.domain import ValueObject


class EventDetails(ValueObject):
    """One event and how many members have said they are going.

    The count travels with the event because everywhere that shows an event shows the
    tally beside it, and letting each of those ask separately is one query per event.
    """

    event: Event
    rsvp_count: int = 0


class EventListingPage(ValueObject):
    """Soonest first, and the instant the next page starts after."""

    events: tuple[EventDetails, ...]
    next_after: datetime | None = None


def as_text(value: datetime | None) -> str | None:
    """An instant in the one form that survives a trip through a query string.

    Written with a `Z`, not a `+00:00`: a `+` in a query string is a space by the time
    it arrives, and a page marker is only any use if it comes back whole.
    """
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")
