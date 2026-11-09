"""One session, one transaction, and both of the context's repositories on it."""

from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.contexts.events.application.unit_of_work import EventsUnitOfWork
from relay.contexts.events.domain.ports import Communities, EventRepository, RsvpRepository
from relay.contexts.events.infrastructure.repository import (
    SqlAlchemyCommunities,
    SqlAlchemyEventRepository,
    SqlAlchemyRsvpRepository,
)
from relay.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyEventsUnitOfWork(SqlAlchemyUnitOfWork, EventsUnitOfWork):
    """The events unit of work, built from the app's session factory.

    One transaction covers both tables on purpose: taking a place reads the event and
    writes the place, and a place saved against an event that was not read in the same
    breath is a place at whatever that row turned out to be. The communities read rides
    along in it, which costs nothing and means a plan filed under a community checks that
    community in the same breath as it writes itself.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(session_factory)

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.events: EventRepository = SqlAlchemyEventRepository(self.session)
        self.rsvps: RsvpRepository = SqlAlchemyRsvpRepository(self.session)
        self.communities: Communities = SqlAlchemyCommunities(self.session)
        return self
