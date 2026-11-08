"""The only way in: nobody signs up without an invite someone already in Relay handed them."""

import secrets
from datetime import datetime

from relay.contexts.auth.domain.errors import InviteNotUsableError, InviteSpentError
from relay.contexts.auth.domain.models import RelationalEntity
from relay.shared.domain import ValueObject

_TOKEN_BYTES = 32


class InviteToken(ValueObject):
    """The string in an invite link. Opaque: Relay never decodes it, it looks it up."""

    value: str

    @classmethod
    def new(cls) -> "InviteToken":
        return cls(value=secrets.token_urlsafe(_TOKEN_BYTES))

    @classmethod
    def parse(cls, raw: str) -> "InviteToken":
        value = raw.strip()
        if not value:
            raise InviteNotUsableError("Relay is invite-only: an invite token is required.")
        return cls(value=value)

    def __str__(self) -> str:
        return self.value


class Invite(RelationalEntity):
    """One invitation, spent by the first person who registers with it and by nobody else."""

    token: InviteToken
    created_by_id: int | None = None
    used_by_id: int | None = None
    used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None

    @classmethod
    def issue(
        cls, *, created_by_id: int | None = None, created_at: datetime | None = None
    ) -> "Invite":
        return cls(token=InviteToken.new(), created_by_id=created_by_id, created_at=created_at)

    @property
    def state(self) -> str:
        """Open until someone registers with it, or an admin takes it back."""
        if self.revoked_at is not None:
            return "revoked"
        if self.used_at is not None:
            return "used"
        return "open"

    @property
    def is_open(self) -> bool:
        return self.state == "open"

    def redeem(self, *, user_id: int, at: datetime) -> None:
        """Spend it. Raises when it is not open, so a second person cannot ride in on it."""
        if not self.is_open:
            raise InviteSpentError(f"That invite is {self.state}.")
        self.used_by_id = user_id
        self.used_at = at

    def revoke(self, *, at: datetime) -> None:
        self.revoked_at = at
