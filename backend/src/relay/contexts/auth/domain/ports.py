"""Ports the auth context needs; infrastructure supplies the implementations."""

from abc import ABC, abstractmethod
from datetime import timedelta


class PasswordHasher(ABC):
    """Turns a password into something safe to store, and checks one back."""

    @abstractmethod
    def hash(self, raw: str) -> str: ...

    @abstractmethod
    def verify(self, raw: str, hashed: str | None) -> bool:
        """Check a password, or none at all when there is no account to check it against.

        The None is on purpose: an implementation still pays the full cost of hashing
        so that a missing account and a wrong password take the same time to answer.
        """


class TokenBroker(ABC):
    """Signs and checks the access tokens Relay vouches for, so a client never vouches for itself.

    Only the short-lived token is a JWT: the database is never consulted to read one.
    Refresh tokens are random strings kept in a table, which is what makes them revocable.
    """

    @abstractmethod
    def access_token_for(self, user_id: int, *, lifetime: timedelta) -> str: ...

    @abstractmethod
    def user_id_of(self, token: str) -> int:
        """Who a bearer token claims to be. Raises InvalidTokenError for anything else."""
