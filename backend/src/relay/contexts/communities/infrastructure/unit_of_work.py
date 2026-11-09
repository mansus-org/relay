"""One session, one transaction, and the three readers a community needs on it."""

from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.contexts.communities.application.unit_of_work import CommunitiesUnitOfWork
from relay.contexts.communities.domain.ports import (
    CommunityFeedReader,
    CommunityRepository,
    MembershipRepository,
)
from relay.contexts.communities.infrastructure.feed import SqlAlchemyCommunityFeedReader
from relay.contexts.communities.infrastructure.repository import (
    SqlAlchemyCommunityRepository,
    SqlAlchemyMembershipRepository,
)
from relay.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyCommunitiesUnitOfWork(SqlAlchemyUnitOfWork, CommunitiesUnitOfWork):
    """The communities unit of work, built from the app's session factory."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(session_factory)

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.communities: CommunityRepository = SqlAlchemyCommunityRepository(self.session)
        self.members: MembershipRepository = SqlAlchemyMembershipRepository(self.session)
        self.feed: CommunityFeedReader = SqlAlchemyCommunityFeedReader(self.session)
        return self
