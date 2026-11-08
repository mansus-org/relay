"""The auth unit of work: one session, three repositories, one commit."""

from relay.contexts.auth.application.unit_of_work import AuthUnitOfWork
from relay.contexts.auth.domain.repository import (
    InviteRepository,
    RefreshTokenRepository,
    UserRepository,
)
from relay.contexts.auth.infrastructure.repositories import (
    SqlAlchemyInviteRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyUserRepository,
)
from relay.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyAuthUnitOfWork(SqlAlchemyUnitOfWork, AuthUnitOfWork):
    """Builds the repositories on the session it is given, so they all share one transaction."""

    @property
    def users(self) -> UserRepository:
        return SqlAlchemyUserRepository(self.session)

    @property
    def invites(self) -> InviteRepository:
        return SqlAlchemyInviteRepository(self.session)

    @property
    def refresh_tokens(self) -> RefreshTokenRepository:
        return SqlAlchemyRefreshTokenRepository(self.session)
