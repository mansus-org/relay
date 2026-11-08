"""A signed-in session. The refresh token is the session: cut it and the device is out."""

from datetime import datetime, timedelta

from relay.contexts.auth.domain.models import RelationalEntity

REFRESH_LIFETIME = timedelta(days=30)


class RefreshToken(RelationalEntity):
    """One device's session. Rotated on every refresh, so a leaked token dies with the swap.

    Only a hash of the token is stored: a dump of this table must not hand out sessions.
    """

    user_id: int
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None = None
    created_at: datetime | None = None

    @classmethod
    def start(
        cls,
        *,
        user_id: int,
        token_hash: str,
        now: datetime,
        lifetime: timedelta = REFRESH_LIFETIME,
    ) -> "RefreshToken":
        return cls(
            user_id=user_id, token_hash=token_hash, expires_at=now + lifetime, created_at=now
        )

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at <= now

    def revoke(self, *, at: datetime) -> None:
        self.revoked_at = at
