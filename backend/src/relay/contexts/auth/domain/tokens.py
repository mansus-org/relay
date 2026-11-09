"""What the API hands out, and what a refresh token looks like while it is in a client's hands."""

import hashlib
import secrets
from datetime import timedelta

from relay.contexts.auth.domain.errors import InvalidTokenError
from relay.shared.domain import ValueObject

_TICKET_BYTES = 32

# An access token is short-lived on purpose: it is the one credential Relay cannot take back.
ACCESS_LIFETIME = timedelta(minutes=15)


class RefreshTicket(ValueObject):
    """The string a client sends back to /auth/refresh. Random, and never stored as-is.

    Only its fingerprint goes in the database, so a dump of the sessions table
    cannot be replayed as sessions.
    """

    value: str

    @classmethod
    def new(cls) -> "RefreshTicket":
        return cls(value=secrets.token_urlsafe(_TICKET_BYTES))

    @classmethod
    def parse(cls, raw: str) -> "RefreshTicket":
        value = raw.strip()
        if not value:
            raise InvalidTokenError("No refresh token given.")
        return cls(value=value)

    def fingerprint(self) -> str:
        """The storable half: one-way, and the only way back to the row."""
        return hashlib.sha256(self.value.encode()).hexdigest()

    def __str__(self) -> str:
        return self.value


class TokenPair(ValueObject):
    """Both tokens, for the two endpoints that open a session: register and login."""

    access_token: str
    refresh_token: RefreshTicket
