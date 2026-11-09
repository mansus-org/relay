"""The auth unit of work: one session, three repositories, one commit."""

from typing import Self

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
    """The repositories are built on the session this opens, so they share one transaction.

    They cannot exist before `async with`: there is no session before it.
    """

    users: UserRepository
    invites: InviteRepository
    refresh_tokens: RefreshTokenRepository

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.users = SqlAlchemyUserRepository(self.session)
        self.invites = SqlAlchemyInviteRepository(self.session)
        self.refresh_tokens = SqlAlchemyRefreshTokenRepository(self.session)
        return self
