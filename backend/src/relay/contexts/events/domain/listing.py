"""What is on: a page of upcoming events, and how many people are going to each."""

from datetime import UTC, datetime
from uuid import UUID

from relay.contexts.events.domain.event import Event, InvalidTimeError, instant
from relay.shared.domain import ValueObject

#: The one word in `from` that means "read the other way": what has already started.
PAST = "past"

#: What joins the parts of a page marker. `~` because it is one of the characters a
#: query string carries without escaping, unlike a space or a `+`.
SEPARATOR = "~"


class ListingStart(ValueObject):
    """Where a page of the listing begins, and which way it reads from there.

    An instant cannot say where a page ended on its own. Hosts pick start times, and a
    town's events all start at seven, so twenty of them can share one `starts_at`: a
    page that resumes at "after seven" either repeats them or skips them. The id of the
    last row read is what makes "after this one" mean one row and not one minute.

    `backwards` is the other direction, and the reason `past` is a word rather than a
    date: a reader asking for what already happened wants the recent part of it, so the
    page reads back from now instead of forwards from the first thing ever filed.
    """

    at: datetime
    after_id: UUID | None = None
    backwards: bool = False

    @classmethod
    def read(cls, value: str | None, *, now: datetime) -> "ListingStart":
        """Where `from` says to start reading: a date, an instant, `past`, or a marker.

        No `from` is the default wall — now, forwards. A date (`2026-03-04`) is that
        midnight in UTC and a full instant is itself, so the same word pages forwards
        from anywhere. `past` flips the direction, and a marker handed back by the page
        before is that same word with the last row of it stuck on the end.
        """
        written = (value or "").strip()
        backwards = written.lower().startswith(PAST)
        if backwards:
            written = written.removeprefix(PAST).removeprefix(SEPARATOR).strip()
        at, _, last = written.partition(SEPARATOR)
        return cls(
            at=instant(at) if at else now,
            after_id=_row(last) if last else None,
            backwards=backwards,
        )

    def as_text(self) -> str:
        """This start in the one form that survives a trip through a query string.

        Written with a `Z`, not a `+00:00`: a `+` in a query string is a space by the
        time it arrives, and a page marker is only any use if it comes back whole.
        """
        written = self.at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        if self.after_id is not None:
            written = f"{written}{SEPARATOR}{self.after_id}"
        return f"{PAST}{SEPARATOR}{written}" if self.backwards else written


def _row(last: str) -> UUID:
    """The row a marker stopped on, or a refusal when no page ever handed that out."""
    try:
        return UUID(last)
    except ValueError as error:
        raise InvalidTimeError("That is not a page Relay handed out.") from error


class EventDetails(ValueObject):
    """One event and how many members have said they are going.

    The count travels with the event because everywhere that shows an event shows the
    tally beside it, and letting each of those ask separately is one query per event.

    `user_rsvped` is the answer to a different question — is *this reader* going — so
    only the read of one event fills it in. The list is public and leaves it false.
    """

    event: Event
    rsvp_count: int = 0
    user_rsvped: bool = False


class EventListingPage(ValueObject):
    """Soonest first, and the marker the next page starts at."""

    events: tuple[EventDetails, ...]
    next_from: ListingStart | None = None
