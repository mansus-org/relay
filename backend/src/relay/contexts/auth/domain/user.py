"""Who someone is: a handle they log in with, a name they are shown by, a hash of their password."""

import re
from datetime import datetime

from relay.contexts.auth.domain.errors import (
    InvalidDisplayNameError,
    InvalidPasswordError,
    InvalidUsernameError,
)
from relay.contexts.auth.domain.models import RelationalEntity
from relay.shared.domain import ValueObject

# A handle you can type on a phone: letters, digits, dot, underscore. No spaces, no accents.
_USERNAME = re.compile(r"^[a-zA-Z0-9_.]{3,20}$")

MIN_PASSWORD_CHARS = 8
# bcrypt reads the first 72 bytes and nothing after them, so a longer password is a false promise.
MAX_PASSWORD_BYTES = 72
# Long enough for a name in any language Relay supports, short enough to fit on a line.
MAX_DISPLAY_NAME_CHARS = 60


class Username(ValueObject):
    """A login handle, unique across Relay."""

    value: str

    @classmethod
    def parse(cls, raw: str) -> "Username":
        """Trim and validate, raising instead of returning None so the caller gets a message."""
        value = raw.strip()
        if not _USERNAME.match(value):
            raise InvalidUsernameError(
                "Usernames are 3-20 characters: letters, numbers, dots and underscores."
            )
        return cls(value=value)

    def __str__(self) -> str:
        return self.value


class Password(ValueObject):
    """A password still in the clear, which is only ever in Relay's memory for a moment."""

    value: str

    @classmethod
    def parse(cls, raw: str) -> "Password":
        if len(raw) < MIN_PASSWORD_CHARS:
            raise InvalidPasswordError(f"Passwords are at least {MIN_PASSWORD_CHARS} characters.")
        if len(raw.encode()) > MAX_PASSWORD_BYTES:
            raise InvalidPasswordError(f"Passwords are at most {MAX_PASSWORD_BYTES} characters.")
        return cls(value=raw)

    def __str__(self) -> str:
        return self.value


class DisplayName(ValueObject):
    """What Relay calls someone out loud. Their own choice, within one line."""

    value: str

    @classmethod
    def parse(cls, raw: str) -> "DisplayName":
        value = raw.strip()
        if not value:
            raise InvalidDisplayNameError("A display name cannot be empty.")
        if len(value) > MAX_DISPLAY_NAME_CHARS:
            raise InvalidDisplayNameError(
                f"Display names are at most {MAX_DISPLAY_NAME_CHARS} characters."
            )
        return cls(value=value)

    def __str__(self) -> str:
        return self.value


class User(RelationalEntity):
    """A Relay account. The password lives here only as a hash."""

    username: Username
    display_name: DisplayName
    password_hash: str
    is_admin: bool = False
    created_at: datetime | None = None

    @classmethod
    def new(
        cls, username: str, display_name: str, password_hash: str, *, is_admin: bool = False
    ) -> "User":
        """Build one from whatever the request had in it; the values decide if it is valid."""
        return cls(
            username=Username.parse(username),
            display_name=DisplayName.parse(display_name),
            password_hash=password_hash,
            is_admin=is_admin,
        )

    @property
    def name(self) -> str:
        """What to call them: what they chose, or their handle when they did not choose one."""
        return str(self.display_name) or str(self.username)
