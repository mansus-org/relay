"""One member going to one event."""

from datetime import datetime
from uuid import UUID

from relay.contexts.events.domain.event import Event
from relay.shared.domain import ConflictError, Entity, ValueObject


class AlreadyRsvpedError(ConflictError):
    """This member is already going, so there is no second place to take."""


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
    """What saying you are going came to.

    `was_new` is the difference between a first tap and a fourth one on the same
    button: both leave you going, and only the first added anything.
    """

    event: Event
    rsvp_count: int
    was_new: bool
