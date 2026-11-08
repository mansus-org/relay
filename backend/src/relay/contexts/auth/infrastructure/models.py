"""The auth tables: accounts, invites, sessions. Nothing outside this package touches them."""

from datetime import UTC, datetime
from typing import overload

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, false, func
from sqlalchemy.orm import Mapped, mapped_column

from relay.contexts.auth.domain.invite import Invite, InviteToken
from relay.contexts.auth.domain.refresh_token import RefreshToken
from relay.contexts.auth.domain.user import DisplayName, User, Username
from relay.shared.infrastructure.database import Base


def _integer_pk() -> Mapped[int]:
    """Row number. SQLite only autoincrements INTEGER, so the type has to follow the database."""
    return mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)


def _utc() -> Mapped[datetime]:
    """A timestamp column that carries no offset: every one of these is UTC."""
    return mapped_column(DateTime())


# Every length here is the domain's own limit, plus room for the format the column holds:
# a bcrypt string is 60 characters, a sha256 fingerprint is 64, an invite token is 43.
USERNAME_LENGTH = 20
DISPLAY_NAME_LENGTH = 60
PASSWORD_HASH_LENGTH = 120
TOKEN_LENGTH = 64


@overload
def naive_utc(value: datetime) -> datetime: ...


@overload
def naive_utc(value: None) -> None: ...


def naive_utc(value: datetime | None) -> datetime | None:
    """Drop the offset on the way in: these columns are UTC with no offset to carry.

    A bare UPDATE has to come through here too, or the two ways of writing would leave
    two different shapes in one column and only one of them would read back right.
    """
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


@overload
def aware_utc(value: datetime) -> datetime: ...


@overload
def aware_utc(value: None) -> None: ...


def aware_utc(value: datetime | None) -> datetime | None:
    """Put the offset back on the way out, so the domain only ever sees aware UTC."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


class UserRow(Base):
    """An account."""

    __tablename__ = "users"

    id: Mapped[int] = _integer_pk()
    username: Mapped[str] = mapped_column(String(USERNAME_LENGTH), unique=True)
    display_name: Mapped[str] = mapped_column(String(DISPLAY_NAME_LENGTH))
    password_hash: Mapped[str] = mapped_column(String(PASSWORD_HASH_LENGTH))
    is_admin: Mapped[bool] = mapped_column(server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())

    @classmethod
    def from_entity(cls, user: User) -> "UserRow":
        return cls(
            id=user.id,
            username=str(user.username),
            display_name=str(user.display_name),
            password_hash=user.password_hash,
            is_admin=user.is_admin,
            created_at=naive_utc(user.created_at),
        )

    def to_entity(self) -> User:
        return User(
            id=self.id,
            username=Username(value=self.username),
            display_name=DisplayName(value=self.display_name),
            password_hash=self.password_hash,
            is_admin=self.is_admin,
            created_at=aware_utc(self.created_at),
        )


class InviteRow(Base):
    """An invite. The token is the whole secret, so it is unique and never guessed."""

    __tablename__ = "invites"

    id: Mapped[int] = _integer_pk()
    token: Mapped[str] = mapped_column(String(TOKEN_LENGTH), unique=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    used_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    used_at: Mapped[datetime | None] = _utc()
    revoked_at: Mapped[datetime | None] = _utc()
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())

    @classmethod
    def from_entity(cls, invite: Invite) -> "InviteRow":
        return cls(
            id=invite.id,
            token=str(invite.token),
            created_by_id=invite.created_by_id,
            used_by_id=invite.used_by_id,
            used_at=naive_utc(invite.used_at),
            revoked_at=naive_utc(invite.revoked_at),
            created_at=naive_utc(invite.created_at),
        )

    def to_entity(self) -> Invite:
        return Invite(
            id=self.id,
            token=InviteToken(value=self.token),
            created_by_id=self.created_by_id,
            used_by_id=self.used_by_id,
            used_at=aware_utc(self.used_at),
            revoked_at=aware_utc(self.revoked_at),
            created_at=aware_utc(self.created_at),
        )


class RefreshTokenRow(Base):
    """One device's session. Only the fingerprint of the token is stored."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = _integer_pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(TOKEN_LENGTH), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), index=True)
    revoked_at: Mapped[datetime | None] = _utc()
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())

    @classmethod
    def from_entity(cls, token: RefreshToken) -> "RefreshTokenRow":
        return cls(
            id=token.id,
            user_id=token.user_id,
            token_hash=token.token_hash,
            expires_at=naive_utc(token.expires_at),
            revoked_at=naive_utc(token.revoked_at),
            created_at=naive_utc(token.created_at),
        )

    def to_entity(self) -> RefreshToken:
        return RefreshToken(
            id=self.id,
            user_id=self.user_id,
            token_hash=self.token_hash,
            expires_at=aware_utc(self.expires_at),
            revoked_at=aware_utc(self.revoked_at),
            created_at=aware_utc(self.created_at),
        )
