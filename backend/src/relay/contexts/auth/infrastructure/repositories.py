"""Reading and writing accounts, invites and sessions."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from relay.contexts.auth.domain.invite import Invite, InviteToken
from relay.contexts.auth.domain.refresh_token import RefreshToken
from relay.contexts.auth.domain.repository import (
    InviteRepository,
    RefreshTokenRepository,
    UserRepository,
)
from relay.contexts.auth.domain.user import User, Username
from relay.contexts.auth.infrastructure.models import InviteRow, RefreshTokenRow, UserRow


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
        row = await self._session.merge(UserRow.from_entity(entity))
        await self._session.flush()
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

    async def count(self) -> int:
        return await self._session.scalar(select(func.count()).select_from(RefreshTokenRow)) or 0
