"""Stand-ins for the auth tables and ports, so a use-case test never has to open a database."""

from datetime import datetime, timedelta

from relay.contexts.auth.application.unit_of_work import AuthUnitOfWork
from relay.contexts.auth.domain.errors import InvalidTokenError
from relay.contexts.auth.domain.invite import Invite, InviteToken
from relay.contexts.auth.domain.ports import PasswordHasher, TokenBroker
from relay.contexts.auth.domain.refresh_token import RefreshToken
from relay.contexts.auth.domain.repository import (
    InviteRepository,
    RefreshTokenRepository,
    UserRepository,
)
from relay.contexts.auth.domain.user import User, Username
from tests.fakes.unit_of_work import FakeUnitOfWork


class _Sequence:
    """Hands out row numbers the way the database would: one more than the last."""

    def __init__(self) -> None:
        self._next = 1

    def next(self) -> int:
        row_id = self._next
        self._next += 1
        return row_id


class InMemoryUserRepository(UserRepository):
    """Accounts in a dict, with the two lookups auth makes."""

    def __init__(self) -> None:
        self._items: dict[int, User] = {}
        self._sequence = _Sequence()

    async def get(self, id: int) -> User | None:
        return self._items.get(id)

    async def get_by_username(self, username: Username) -> User | None:
        return next((user for user in self._items.values() if user.username == username), None)

    async def add(self, entity: User) -> None:
        if entity.id is None:
            entity.id = self._sequence.next()
        self._items[entity.id] = entity

    async def count(self) -> int:
        return len(self._items)


class InMemoryInviteRepository(InviteRepository):
    """Invites, found by the token from the link."""

    def __init__(self, *, somebody_else_won: bool = False) -> None:
        self._items: dict[int, Invite] = {}
        self._sequence = _Sequence()
        # Set this to be the other writer who got there first: every spend is refused even
        # though the copy in here still looks open, which is what the real UPDATE does when
        # its WHERE matches no row.
        self.somebody_else_won = somebody_else_won

    async def get(self, id: int) -> Invite | None:
        return self._items.get(id)

    async def get_by_token(self, token: InviteToken) -> Invite | None:
        return next((invite for invite in self._items.values() if invite.token == token), None)

    async def add(self, entity: Invite) -> None:
        if entity.id is None:
            entity.id = self._sequence.next()
        self._items[entity.id] = entity

    async def redeem(self, invite: Invite, *, user_id: int, at: datetime) -> bool:
        """Spend it, and say False when somebody already did."""
        if self.somebody_else_won or not invite.is_open:
            return False
        invite.redeem(user_id=user_id, at=at)
        return True


class InMemoryRefreshTokenRepository(RefreshTokenRepository):
    """Sessions, found by the fingerprint of the token."""

    def __init__(self, *, somebody_else_won: bool = False) -> None:
        self._items: dict[int, RefreshToken] = {}
        self._sequence = _Sequence()
        # Same as the invites: every end-of-session is refused, as if another writer had
        # already put a revoked_at on the row.
        self.somebody_else_won = somebody_else_won

    async def get(self, id: int) -> RefreshToken | None:
        return self._items.get(id)

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        return next(
            (token for token in self._items.values() if token.token_hash == token_hash), None
        )

    async def add(self, entity: RefreshToken) -> None:
        if entity.id is None:
            entity.id = self._sequence.next()
        self._items[entity.id] = entity

    async def revoke(self, token: RefreshToken, *, at: datetime) -> bool:
        """End it, and say False when it was already over."""
        if self.somebody_else_won or not token.is_active:
            return False
        token.revoke(at=at)
        return True


class FakeAuthUnitOfWork(FakeUnitOfWork, AuthUnitOfWork):
    """The three repositories sharing one fake transaction.

    `somebody_else_won` is the race switch: with it set, every spend and every
    end-of-session comes back refused, exactly as it does for the request that loses.
    """

    def __init__(self, *, somebody_else_won: bool = False) -> None:
        super().__init__()
        self.users = InMemoryUserRepository()
        self.invites = InMemoryInviteRepository(somebody_else_won=somebody_else_won)
        self.refresh_tokens = InMemoryRefreshTokenRepository(somebody_else_won=somebody_else_won)


class PlainPasswordHasher(PasswordHasher):
    """Not a hash: it makes the answer obvious, so a test can assert on what was stored.

    Never ship it. It exists so a test can say "the password was stored" without
    waiting on bcrypt, and so a wrong password fails for the right reason.
    """

    def hash(self, raw: str) -> str:
        return f"hashed:{raw}"

    def verify(self, raw: str, hashed: str | None) -> bool:
        return hashed is not None and hashed == self.hash(raw)


class CountingTokenBroker(TokenBroker):
    """Access tokens that are a user id in a coat: no signature, no expiry, no surprises."""

    def __init__(self) -> None:
        self.issued: list[int] = []

    def access_token_for(self, user_id: int, *, lifetime: timedelta) -> str:
        self.issued.append(user_id)
        return f"access:{user_id}:{int(lifetime.total_seconds())}"

    def user_id_of(self, token: str) -> int:
        try:
            _, user_id, _ = token.split(":")
            return int(user_id)
        except (ValueError, AttributeError) as error:
            raise InvalidTokenError("That access token is not one of ours.") from error
