"""Auth domain: accounts, invites, sessions, and the rules for each. No framework imports here."""

from relay.contexts.auth.domain.errors import (
    AuthError,
    InvalidCredentialsError,
    InvalidDisplayNameError,
    InvalidPasswordError,
    InvalidTokenError,
    InvalidUsernameError,
    InviteNotUsableError,
    UsernameTakenError,
)
from relay.contexts.auth.domain.invite import Invite, InviteToken
from relay.contexts.auth.domain.models import RelationalEntity
from relay.contexts.auth.domain.ports import PasswordHasher, TokenBroker
from relay.contexts.auth.domain.refresh_token import REFRESH_LIFETIME, RefreshToken
from relay.contexts.auth.domain.repository import (
    InviteRepository,
    RefreshTokenRepository,
    UserRepository,
)
from relay.contexts.auth.domain.tokens import ACCESS_LIFETIME, RefreshTicket, TokenPair
from relay.contexts.auth.domain.user import (
    MAX_DISPLAY_NAME_CHARS,
    MAX_PASSWORD_BYTES,
    MIN_PASSWORD_CHARS,
    DisplayName,
    Password,
    User,
    Username,
)

__all__ = [
    "ACCESS_LIFETIME",
    "MAX_DISPLAY_NAME_CHARS",
    "MAX_PASSWORD_BYTES",
    "MIN_PASSWORD_CHARS",
    "REFRESH_LIFETIME",
    "AuthError",
    "DisplayName",
    "InvalidCredentialsError",
    "InvalidDisplayNameError",
    "InvalidPasswordError",
    "InvalidTokenError",
    "InvalidUsernameError",
    "Invite",
    "InviteNotUsableError",
    "InviteRepository",
    "InviteToken",
    "Password",
    "PasswordHasher",
    "RefreshTicket",
    "RefreshToken",
    "RefreshTokenRepository",
    "RelationalEntity",
    "TokenBroker",
    "TokenPair",
    "User",
    "UserRepository",
    "Username",
    "UsernameTakenError",
]
