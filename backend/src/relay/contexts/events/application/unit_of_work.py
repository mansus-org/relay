"""The events unit of work: one transaction that can reach the events and the rsvps."""

from relay.contexts.events.domain.ports import EventRepository, RsvpRepository
from relay.shared.application import UnitOfWork


class EventsUnitOfWork(UnitOfWork):
    """A transaction over both tables of the context. Implementations set them on entry."""

    events: EventRepository
    rsvps: RsvpRepository
