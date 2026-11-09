"""The events unit of work: one transaction over its own tables and a read of the communities."""

from relay.contexts.events.domain.ports import Communities, EventRepository, RsvpRepository
from relay.shared.application import UnitOfWork


class EventsUnitOfWork(UnitOfWork):
    """A transaction over the context's tables, plus the one thing it may read from another.

    `communities` only ever reads: names, and whether someone belongs. Everything else
    about a community stays in the communities context. Implementations set them on entry.
    """

    events: EventRepository
    rsvps: RsvpRepository
    communities: Communities
