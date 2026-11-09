"""One member going to one event."""

from datetime import datetime
from uuid import UUID

from relay.contexts.events.domain.event import Event
from relay.shared.domain import ConflictError, Entity, NotFoundError, ValueObject


class AlreadyRsvpedError(ConflictError):
    """This member is already going, so there is no second place to take."""


class NotGoingError(NotFoundError):
    """There is no place of this member's at this event to give back."""


class Rsvp(Entity):
    """One member's place at one event.

    One row per event and member, and the table says so with a unique index; this
    class only makes the pair easy to hand around.
    """

    event_id: UUID
    member_id: UUID
    created_at: datetime

    @classmethod
    def go(cls, *, event_id: UUID, member_id: UUID, at: datetime) -> "Rsvp":
        """The one way a place is taken."""
        return cls(event_id=event_id, member_id=member_id, created_at=at)


class RsvpOutcome(ValueObject):
    """What saying you are going came to: the event, and the tally once this one is in.

    The tally is read after the place was written, so it counts you. It is not a lock:
    someone else's place can arrive in the same moment and be counted too.
    """

    event: Event
    rsvp_count: int
