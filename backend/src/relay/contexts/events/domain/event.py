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


def instant(value: datetime | str) -> datetime:
    """A time as an instant in UTC, or InvalidTimeError saying it is not a time.

    A string is read the way a cursor is read, because it is one: `next_after` is
    handed back as a query parameter and has to survive the trip. A datetime that
    names no zone is read as UTC, because UTC is the zone events are stored in and a
    start time kept in another one would compare off by its offset.
    """
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.strip())
        except ValueError as error:
            raise InvalidTimeError("That is not a time Relay can read.") from error
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


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
        starts = instant(starts_at)
        ends = instant(ends_at) if ends_at is not None else None
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
            created_at=created_at,
        )
