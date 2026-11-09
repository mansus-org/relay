"""The transaction auth use cases run in."""

from relay.contexts.auth.domain.repository import (
    InviteRepository,
    RefreshTokenRepository,
    UserRepository,
)
from relay.shared.application import UnitOfWork


class AuthUnitOfWork(UnitOfWork):
    """One transaction over accounts, invites and sessions."""

    users: UserRepository
    invites: InviteRepository
    refresh_tokens: RefreshTokenRepository
