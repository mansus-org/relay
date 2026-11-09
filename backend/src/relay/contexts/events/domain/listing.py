"""What is on: a page of a locality's events, and how many people are going to each."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from pydantic import field_validator

from relay.contexts.events.domain.event import Event, instant
from relay.shared.domain import ValidationError, ValueObject

#: The one word in `from` that means "read the other way": what has already started.
PAST = "past"

#: What joins the parts of a page marker. `~` because it is one of the characters a
#: query string carries without escaping, unlike a space or a `+`.
SEPARATOR = "~"


class UnknownPageError(ValidationError):
    """Not a place in the listing that Relay ever handed out."""


class ListingStart(ValueObject):
    """Where a page of the listing begins, and which way it reads from there.

    An instant cannot say where a page ended on its own. Hosts pick start times, and a
    town's events all start at seven, so twenty of them can share one `starts_at`: a
    page that resumes at "after seven" either repeats them or skips them. The id of the
    row the page stopped on is what makes "after this one" mean one row and not one
    minute.

    `backwards` is the other direction, and the reason `past` is a word rather than a
    date: a reader asking for what already happened wants the recent part of it, so the
    page reads back from now instead of forwards from the first thing ever filed.
    """

    at: datetime
    seen_id: UUID | None = None
    backwards: bool = False

    @field_validator("at")
    @classmethod
    def _zone_named(cls, at: datetime) -> datetime:
        """Kept in UTC, and never a time that forgot to say which zone it is in.

        A zone-less time would be read as the machine's own clock, and the page would
        cut at a different instant on every machine that runs it.
        """
        if at.tzinfo is None:
            raise ValidationError("A page starts from a time that says which zone it is in.")
        return at.astimezone(UTC)

    @classmethod
    def read(cls, value: str | None, *, now: datetime) -> "ListingStart":
        """Where `from` says to start reading, in this grammar and no other::

            past
            <wall>
            <wall>~<id>
            past~<wall>
            past~<wall>~<id>

        A `<wall>` is a date (`2026-03-04`, read as its midnight in UTC) or a full
        instant, so the same word pages from anywhere. An empty `from` reads forwards
        from now; `past` alone reads backwards from now. The `<wall>~<id>` shape is the
        marker a page handed back: the row it stopped on, and the direction to keep
        reading in.
        """
        written = (value or "").strip()
        if not written:
            return cls(at=now)
        parts = written.split(SEPARATOR)
        backwards = parts[0].lower() == PAST
        if backwards:
            parts = parts[1:]
        if len(parts) > 2 or not all(parts):
            raise UnknownPageError("That is not a page Relay handed out.")
        wall = parts[0] if parts else ""
        last = parts[1] if len(parts) == 2 else ""
        return cls(
            at=instant(wall) if wall else now,
            seen_id=_row(last) if last else None,
            backwards=backwards,
        )

    def as_text(self) -> str:
        """This start in the one form that survives a trip through a query string.

        Written with a `Z`, not a `+00:00`: a `+` in a query string is a space by the
        time it arrives, and a page marker is only any use if it comes back whole.
        """
        written = self.at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        if self.seen_id is not None:
            written = f"{written}{SEPARATOR}{self.seen_id}"
        return f"{PAST}{SEPARATOR}{written}" if self.backwards else written


def _row(last: str) -> UUID:
    """The row a marker stopped on, or a refusal when no page ever handed that out."""
    try:
        return UUID(last)
    except ValueError as error:
        raise UnknownPageError("That is not a page Relay handed out.") from error


def marker_after(events: Sequence[Event], start: ListingStart) -> ListingStart:
    """Where the next page starts: the last row of this one, reading the same way.

    Both lists a page of events is served from — a locality's and a community's — cut
    their pages the same way, so the marker is built in one place and cannot drift.
    """
    last = events[-1]
    return ListingStart(at=last.starts_at, seen_id=last.id, backwards=start.backwards)


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
    # What the community it was filed under is called, so a list can say where an event
    # came from instead of sending its reader to ask. None when it was filed under none.
    community_name: str | None = None


class EventListingPage(ValueObject):
    """The rows of one page, in the order they were read, and the marker for the next."""

    events: tuple[EventDetails, ...]
    next_from: ListingStart | None = None
