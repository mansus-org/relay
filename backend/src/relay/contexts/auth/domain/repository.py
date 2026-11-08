"""Collection-shaped access to the three auth tables."""

from abc import abstractmethod
from datetime import datetime

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

    @abstractmethod
    async def redeem(self, invite: Invite, *, user_id: int, at: datetime) -> bool:
        """Spend an invite on an account, and say whether it was still there to spend.

        The whole point is that this is one atomic write: two people who race each other
        to the same link get one True and one False, not two accounts.
        """


class RefreshTokenRepository(Repository[RefreshToken, int]):
    """Sessions. A token is never stored, so lookups go by its fingerprint."""

    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None: ...

    @abstractmethod
    async def revoke(self, token: RefreshToken, *, at: datetime) -> bool:
        """End one session, and say whether it was still running.

        Rotating a token goes through here, so the answer is also the lock: whoever
        gets False was replaying something already spent and must not be issued a pair.
        """
