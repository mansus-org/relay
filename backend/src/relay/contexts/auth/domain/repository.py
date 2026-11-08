"""Collection-shaped access to the three auth tables."""

from abc import abstractmethod

from relay.contexts.auth.domain.invite import Invite, InviteToken
from relay.contexts.auth.domain.refresh_token import RefreshToken
from relay.contexts.auth.domain.user import User, Username
from relay.shared.domain import Repository


class UserRepository(Repository[User, int]):
    """Accounts, by row number and by handle."""

    @abstractmethod
    async def get_by_username(self, username: Username) -> User | None: ...

    @abstractmethod
    async def count(self) -> int:
        """How many accounts there are. None yet means Relay has no anyone in it."""


class InviteRepository(Repository[Invite, int]):
    """Invites, looked up by the token from the link rather than by id."""

    @abstractmethod
    async def get_by_token(self, token: InviteToken) -> Invite | None: ...


class RefreshTokenRepository(Repository[RefreshToken, int]):
    """Sessions. A token is never stored, so lookups go by its fingerprint."""

    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None: ...
