"""Stand-ins for the auth tables and ports, so a use-case test never has to open a database."""

from datetime import timedelta

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

    def __init__(self) -> None:
        self._items: dict[int, Invite] = {}
        self._sequence = _Sequence()

    async def get(self, id: int) -> Invite | None:
        return self._items.get(id)

    async def get_by_token(self, token: InviteToken) -> Invite | None:
        return next((invite for invite in self._items.values() if invite.token == token), None)

    async def add(self, entity: Invite) -> None:
        if entity.id is None:
            entity.id = self._sequence.next()
        self._items[entity.id] = entity


class InMemoryRefreshTokenRepository(RefreshTokenRepository):
    """Sessions, found by the fingerprint of the token."""

    def __init__(self) -> None:
        self._items: dict[int, RefreshToken] = {}
        self._sequence = _Sequence()

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


class FakeAuthUnitOfWork(FakeUnitOfWork, AuthUnitOfWork):
    """The three repositories sharing one fake transaction."""

    def __init__(self) -> None:
        super().__init__()
        self.users = InMemoryUserRepository()
        self.invites = InMemoryInviteRepository()
        self.refresh_tokens = InMemoryRefreshTokenRepository()


class PlainPasswordHasher(PasswordHasher):
    """Not a hash: it makes the answer obvious, so a test can assert on what was stored.

    Never ship it. It exists so a test can say "the password was stored" without
    waiting on bcrypt, and so a wrong password fails for the right reason.
    """

    def hash(self, raw: str) -> str:
        return f"hashed:{raw}"

    def verify(self, raw: str, hashed: str) -> bool:
        return hashed == self.hash(raw)


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
