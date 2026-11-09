"""An event: something happening at a time and in a place, said by someone."""

from datetime import UTC, datetime
from uuid import UUID

from relay.shared.domain import Entity, NotFoundError, ValidationError

#: A title is the one line an invitation is scanned for. Longer than this and it is
#: the details, not the title.
MAX_TITLE_LENGTH = 200

#: The most anyone is asked to read about an event before deciding. A page, not a
#: book: past this the description belongs somewhere else and linked to.
MAX_DETAILS_LENGTH = 2000

#: Where it happens, as the host writes it: a pub name, a hall, a gate. It is a line,
#: and the cell is what makes it findable, so nothing longer than a line is kept.
MAX_VENUE_LENGTH = 200


class EventNotFoundError(NotFoundError):
    """There is no event to show under that id."""


class InvalidTimeError(ValidationError):
    """Not a time an event can be planned for."""


def _read(value: datetime | str) -> datetime:
    """A time as it was written, zone and all, or InvalidTimeError saying it is not a time."""
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip())
        except ValueError as error:
            raise InvalidTimeError("That is not a time Relay can read.") from error
    return value


def instant(value: datetime | str) -> datetime:
    """A time as an instant in UTC, or InvalidTimeError saying it is not a time.

    A string is read the way a cursor is read, because it is one: `next_from` is handed
    back as a query parameter and has to survive the trip. A datetime that names no zone
    is read as UTC, because UTC is the zone events are stored in and a time kept in
    another one would compare off by its offset. An event's own start is read with
    `zoned_instant` instead, which refuses the zone-less case rather than guessing.
    """
    read = _read(value)
    if read.tzinfo is None:
        read = read.replace(tzinfo=UTC)
    try:
        return read.astimezone(UTC)
    except OverflowError as error:
        # `0001-01-01T00:00:00+01:00` is a real time and no datetime can name it as UTC.
        raise InvalidTimeError("That is not a time Relay can read.") from error


def zoned_instant(value: datetime | str) -> datetime:
    """An instant that says which zone it is in, or InvalidTimeError saying it does not.

    A host's half past seven is half past seven somewhere, and read without a zone it is
    half past seven in UTC: a different evening in every other one. A phone that sends
    local wall clock would file the event hours off and never be told, so a time that
    does not say is refused rather than guessed at.
    """
    read = _read(value)
    if read.tzinfo is None:
        raise InvalidTimeError("An event time has to say which zone it is in.")
    return instant(read)


class Event(Entity):
    """One event.

    `location_cell` is what puts it in a locality's list of what is on. An event with
    no cell exists but reaches nobody; that is the host's problem, not a reason to
    refuse the write — a plan whose place is not settled yet is still a plan.
    """

    host_id: UUID
    title: str
    starts_at: datetime
    ends_at: datetime | None = None
    venue_name: str | None = None
    details: str | None = None
    location_cell: str | None = None
    # The community it was filed under, if it was. A community is people rather than a
    # place, so this says nothing about where it happens: filing it under one is how a
    # book club's night gets onto the book club's own list, cell or no cell beside it.
    community_id: UUID | None = None
    created_at: datetime

    @classmethod
    def plan(
        cls,
        *,
        host_id: UUID,
        title: str,
        starts_at: datetime | str,
        created_at: datetime,
        ends_at: datetime | str | None = None,
        venue_name: str | None = None,
        details: str | None = None,
        location_cell: str | None = None,
        community_id: UUID | None = None,
    ) -> "Event":
        """The one way a new event is made, so nothing is saved without a what and a when."""
        named = title.strip()
        if not named:
            raise ValidationError("An event needs a title.")
        if len(named) > MAX_TITLE_LENGTH:
            raise ValidationError(f"An event title is at most {MAX_TITLE_LENGTH} characters.")
        described = (details or "").strip()
        if len(described) > MAX_DETAILS_LENGTH:
            raise ValidationError(
                f"An event description is at most {MAX_DETAILS_LENGTH} characters."
            )
        where = (venue_name or "").strip()
        if len(where) > MAX_VENUE_LENGTH:
            raise ValidationError(f"A venue is named in at most {MAX_VENUE_LENGTH} characters.")
        starts = zoned_instant(starts_at)
        # An end sent as blanks is a form field cleared, not a time: the event goes on
        # for as long as it goes on, which is what not saying when reads as.
        written_end = ends_at
        if isinstance(written_end, str) and not written_end.strip():
            written_end = None
        ends = zoned_instant(written_end) if written_end is not None else None
        if ends is not None and ends <= starts:
            raise ValidationError("An event cannot end at or before it starts.")
        return cls(
            host_id=host_id,
            title=named,
            starts_at=starts,
            ends_at=ends,
            venue_name=where or None,
            details=described or None,
            location_cell=location_cell or None,
            community_id=community_id,
            created_at=created_at,
        )
