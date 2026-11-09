"""The only way in: nobody signs up without an invite someone already in Relay handed them."""

import secrets
from datetime import datetime

from relay.contexts.auth.domain.errors import (
    InviteNoteTooLongError,
    InviteNotUsableError,
    InviteSpentError,
)
from relay.contexts.auth.domain.models import RelationalEntity
from relay.shared.domain import ValueObject

_TOKEN_BYTES = 32
# An invite note says who the invite was set aside for. Past a short line it is a message,
# and a message belongs in the email you send with the link, not in the invite row.
MAX_NOTE_LENGTH = 200


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
    note: str | None = None

    @classmethod
    def issue(
        cls,
        *,
        created_by_id: int | None = None,
        created_at: datetime | None = None,
        note: str | None = None,
    ) -> "Invite":
        """Make a new invite. `note` is who it was set aside for, and is optional."""
        trimmed = note.strip() if note else None
        if trimmed is not None and len(trimmed) > MAX_NOTE_LENGTH:
            raise InviteNoteTooLongError(f"An invite note is at most {MAX_NOTE_LENGTH} characters.")
        return cls(
            token=InviteToken.new(),
            created_by_id=created_by_id,
            created_at=created_at,
            note=trimmed or None,
        )

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
