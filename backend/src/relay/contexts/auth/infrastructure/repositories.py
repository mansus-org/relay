"""Reading and writing accounts, invites and sessions."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import Result, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relay.contexts.auth.domain.errors import UsernameTakenError
from relay.contexts.auth.domain.invite import Invite, InviteToken
from relay.contexts.auth.domain.refresh_token import RefreshToken
from relay.contexts.auth.domain.repository import (
    InviteRepository,
    RefreshTokenRepository,
    UserRepository,
)
from relay.contexts.auth.domain.user import User, Username
from relay.contexts.auth.infrastructure.models import (
    InviteRow,
    RefreshTokenRow,
    UserRow,
    naive_utc,
)


def _somebody_else_got_there_first(error: IntegrityError) -> bool:
    """Whether the database objected to this username being taken.

    SQLite names the column and Postgres names the constraint, so this listens for the
    objection and the column rather than one exact sentence. Anything else the database
    objected to is not ours to rename.
    """
    reason = str(error.orig).lower()
    return "unique" in reason and "username" in reason


def rows_changed(result: Result[Any]) -> int:
    """How many rows an UPDATE moved.

    SQLAlchemy only promises `Result` back from `execute`, and `Result` has no rowcount; an
    UPDATE really returns a CursorResult, so this says the quiet part once instead of twice.
    """
    return cast("CursorResult[Any]", result).rowcount


class SqlAlchemyUserRepository(UserRepository):
    """Accounts, by row number and by handle."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: int) -> User | None:
        row = await self._session.get(UserRow, id)
        return row.to_entity() if row else None

    async def get_by_username(self, username: Username) -> User | None:
        row = await self._session.scalar(select(UserRow).where(UserRow.username == str(username)))
        return row.to_entity() if row else None

    async def add(self, entity: User) -> None:
        try:
            row = await self._session.merge(UserRow.from_entity(entity))
            await self._session.flush()
        except IntegrityError as error:
            # Somebody took this handle between our look and our write. The unique index is
            # the only thing here that can promise who won, so it is what we listen to -
            # and anything else the database objected to is still passed on as it was.
            if not _somebody_else_got_there_first(error):
                raise
            raise UsernameTakenError("Someone already has that username.") from error
        entity.id = row.id

    async def count(self) -> int:
        return await self._session.scalar(select(func.count()).select_from(UserRow)) or 0


class SqlAlchemyInviteRepository(InviteRepository):
    """Invites, found by the token from the link rather than by id."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: int) -> Invite | None:
        row = await self._session.get(InviteRow, id)
        return row.to_entity() if row else None

    async def get_by_token(self, token: InviteToken) -> Invite | None:
        row = await self._session.scalar(select(InviteRow).where(InviteRow.token == str(token)))
        return row.to_entity() if row else None

    async def add(self, entity: Invite) -> None:
        row = await self._session.merge(InviteRow.from_entity(entity))
        await self._session.flush()
        entity.id = row.id

    async def redeem(self, invite: Invite, *, user_id: int, at: datetime) -> bool:
        # One statement, with "still open" in its WHERE: the database decides which of two
        # people racing the same link wins, and the loser is the one that changes no row.
        # The invite this session already loaded is left as it was read; nothing looks at it
        # again in this transaction, and keeping it in step would cost a second statement.
        result = await self._session.execute(
            update(InviteRow)
            .where(
                InviteRow.id == invite.require_id(),
                InviteRow.used_at.is_(None),
                InviteRow.revoked_at.is_(None),
            )
            .values(used_by_id=user_id, used_at=naive_utc(at))
            .execution_options(synchronize_session=False)
        )
        if rows_changed(result) == 0:
            return False
        invite.redeem(user_id=user_id, at=at)
        return True

    async def count(self) -> int:
        return await self._session.scalar(select(func.count()).select_from(InviteRow)) or 0


class SqlAlchemyRefreshTokenRepository(RefreshTokenRepository):
    """Sessions. The token never reaches these rows, so lookups go by its fingerprint."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: int) -> RefreshToken | None:
        row = await self._session.get(RefreshTokenRow, id)
        return row.to_entity() if row else None

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        row = await self._session.scalar(
            select(RefreshTokenRow).where(RefreshTokenRow.token_hash == token_hash)
        )
        return row.to_entity() if row else None

    async def add(self, entity: RefreshToken) -> None:
        row = await self._session.merge(RefreshTokenRow.from_entity(entity))
        await self._session.flush()
        entity.id = row.id

    async def revoke(self, token: RefreshToken, *, at: datetime) -> bool:
        # Same trick as spending an invite: only a session that is still running is touched,
        # so whoever is replaying a spent ticket finds nothing to spend and gets False. The
        # row loaded above is left stale on purpose, same as there.
        result = await self._session.execute(
            update(RefreshTokenRow)
            .where(
                RefreshTokenRow.id == token.require_id(),
                RefreshTokenRow.revoked_at.is_(None),
            )
            .values(revoked_at=naive_utc(at))
            .execution_options(synchronize_session=False)
        )
        if rows_changed(result) == 0:
            return False
        token.revoke(at=at)
        return True

    async def count(self) -> int:
        return await self._session.scalar(select(func.count()).select_from(RefreshTokenRow)) or 0
