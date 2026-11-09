"""One session, one transaction, and the four repositories an admin's decision touches."""

from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.contexts.admin.application.unit_of_work import ModerationUnitOfWork
from relay.contexts.admin.infrastructure.repositories import (
    SqlAlchemyInvitationRepository,
    SqlAlchemyMemberRepository,
    SqlAlchemyModeratedPostRepository,
    SqlAlchemyModerationLogRepository,
)
from relay.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyModerationUnitOfWork(SqlAlchemyUnitOfWork, ModerationUnitOfWork):
    """The moderation unit of work, built from the app's session factory.

    One session across four repositories over three contexts' tables, which is the point:
    a decision and the line that records it are one commit or neither.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(session_factory)

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.posts = SqlAlchemyModeratedPostRepository(self.session)
        self.log = SqlAlchemyModerationLogRepository(self.session)
        self.members = SqlAlchemyMemberRepository(self.session)
        self.invites = SqlAlchemyInvitationRepository(self.session)
        return self
