"""Statements over the trail, the member list and the invites, and the classes that run them."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.engine import CursorResult, Row
from sqlalchemy.ext.asyncio import AsyncSession

from relay.contexts.admin.domain.members import MemberSummary
from relay.contexts.admin.domain.moderation_log import ModerationLog, ModerationTrigger
from relay.contexts.admin.domain.ports import (
    InvitationRepository,
    MemberRepository,
    ModeratedPostRepository,
    ModerationLogRepository,
)
from relay.contexts.admin.infrastructure.models import (
    ModerationLogRow,
    aware_utc,
    naive_utc,
)
from relay.contexts.auth.domain.invite import Invite
from relay.contexts.auth.infrastructure.models import InviteRow, RefreshTokenRow, UserRow
from relay.contexts.posts.domain.post import ModerationStatus, Post, PostNotFoundError
from relay.contexts.posts.infrastructure.models import PostModel


async def page_of(
    session: AsyncSession,
    statement: Select[Any],
    limit: int,
    offset: int,
    *,
    count: Select[Any] | None = None,
) -> tuple[list[Row[Any]], int]:
    """One page of a statement, and how many rows the whole statement has behind it.

    The total defaults to the same statement with its columns swapped for a count, so the
    number at the top of a list can never be answering a different question from the list
    under it. A list that knows a cheaper way to count its own rows passes that in instead.
    """
    counted = (
        count
        if count is not None
        else select(func.count()).select_from(statement.order_by(None).subquery())
    )
    rows = list((await session.execute(statement.limit(limit).offset(offset))).unique())
    total = (await session.execute(counted)).scalar_one()
    return rows, total


def _changed(result: CursorResult[Any]) -> int:
    """How many rows a write took. The driver reports none at all until it has run."""
    return int(result.rowcount or 0)


class SqlAlchemyModerationLogRepository(ModerationLogRepository):
    """The trail: written once by a decision, read back by whoever has to answer for it."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: int) -> ModerationLog | None:
        row = await self._session.get(ModerationLogRow, id)
        return row.to_domain() if row is not None else None

    async def add(self, entity: ModerationLog) -> None:
        self._session.add(ModerationLogRow.from_domain(entity))

    async def page(
        self,
        *,
        post_id: UUID | None = None,
        community_id: UUID | None = None,
        target_user_id: int | None = None,
        actor_id: int | None = None,
        limit: int,
        offset: int,
    ) -> tuple[list[ModerationLog], int]:
        statement = select(ModerationLogRow)
        for column, value in (
            (ModerationLogRow.post_id, post_id),
            (ModerationLogRow.community_id, community_id),
            (ModerationLogRow.target_user_id, target_user_id),
            (ModerationLogRow.actor_id, actor_id),
        ):
            if value is not None:
                statement = statement.where(column == value)
        statement = statement.order_by(
            ModerationLogRow.created_at.desc(), ModerationLogRow.id.desc()
        )
        rows, total = await page_of(self._session, statement, limit, offset)
        return [row[0].to_domain() for row in rows], total

    async def ai_decisions(self, post_ids: Sequence[UUID]) -> dict[UUID, dict]:
        if not post_ids:
            return {}
        rows = (
            await self._session.execute(
                select(ModerationLogRow.post_id, ModerationLogRow.ai_decision)
                .where(
                    ModerationLogRow.post_id.in_(list(post_ids)),
                    ModerationLogRow.trigger == ModerationTrigger.AI.value,
                    ModerationLogRow.ai_decision.is_not(None),
                )
                .order_by(ModerationLogRow.created_at.desc(), ModerationLogRow.id.desc())
            )
        ).all()
        # Newest first, so the first one seen for a post is the one that still stands.
        newest: dict[UUID, dict] = {}
        for row in rows:
            post_id, decision = row[0], row[1]
            if post_id is not None and decision is not None and post_id not in newest:
                newest[post_id] = decision
        return newest


class SqlAlchemyModeratedPostRepository(ModeratedPostRepository):
    """Posts as somebody running a Relay sees them, including the ones nobody can read."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, post_id: UUID) -> Post:
        row = await self._session.get(PostModel, post_id)
        if row is None:
            raise PostNotFoundError(f"There is no post {post_id} to decide about.")
        return row.to_domain()

    async def page(
        self, *, status: ModerationStatus | None, limit: int, offset: int
    ) -> tuple[list[Post], int]:
        statement = select(PostModel)
        if status is not None:
            statement = statement.where(PostModel.moderation_status == status.value)
        statement = statement.order_by(PostModel.created_at.desc(), PostModel.id.desc())
        rows, total = await page_of(self._session, statement, limit, offset)
        return [row[0].to_domain() for row in rows], total

    async def set_status(self, post: Post, *, to: ModerationStatus, was: ModerationStatus) -> bool:
        statement = (
            update(PostModel)
            .where(
                PostModel.id == post.id,
                PostModel.moderation_status == was.value,
            )
            .values(moderation_status=to.value)
        )
        # The old status is part of the WHERE, so a decision made in another request a
        # moment ago turns this into zero rows instead of quietly overruling it.
        moved = cast("CursorResult[Any]", await self._session.execute(statement))
        return _changed(moved) > 0


def _member_filters(
    statement: Select, *, search: str | None, is_admin: bool | None, deactivated: bool | None
) -> Select:
    """The member list's filters, in one place, so a page and its total cannot drift apart."""
    if search:
        needle = _wildcard(search)
        statement = statement.where(
            or_(
                UserRow.username.ilike(needle, escape="\\"),
                UserRow.display_name.ilike(needle, escape="\\"),
            )
        )
    if is_admin is not None:
        statement = statement.where(UserRow.is_admin.is_(is_admin))
    if deactivated is not None:
        off = UserRow.deactivated_at.is_not(None)
        statement = statement.where(off if deactivated else ~off)
    return statement


def _wildcard(term: str) -> str:
    """A contains-pattern out of whatever was typed, with its own wildcards kept quiet.

    A search for `100%` should look for a name with a percent sign in it, not turn up
    everybody.
    """
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def members_statement(
    *, search: str | None, is_admin: bool | None, deactivated: bool | None
) -> Select:
    """The member list: one row per account, newest first.

    Built here so the query a page of members runs is the query a test can put under
    EXPLAIN, and so `get` and `page` cannot drift into two different ideas of what a row
    about an account is.
    """
    statement = _member_filters(
        select(
            UserRow.id,
            UserRow.username,
            UserRow.display_name,
            UserRow.is_admin,
            UserRow.created_at,
            UserRow.deactivated_at,
        ),
        search=search,
        is_admin=is_admin,
        deactivated=deactivated,
    )
    return statement.order_by(UserRow.created_at.desc(), UserRow.id.desc())


def _summary(row: Row[Any]) -> MemberSummary:
    """One row of the member statement, as the domain wants it."""
    return MemberSummary(
        id=row.id,
        username=row.username,
        display_name=row.display_name,
        is_admin=row.is_admin,
        created_at=aware_utc(row.created_at),
        deactivated_at=aware_utc(row.deactivated_at) if row.deactivated_at else None,
    )


class SqlAlchemyMemberRepository(MemberRepository):
    """Accounts, counted up, and the two writes an admin has over them."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, member_id: int) -> MemberSummary | None:
        statement = members_statement(search=None, is_admin=None, deactivated=None).where(
            UserRow.id == member_id
        )
        row = (await self._session.execute(statement)).first()
        return _summary(row) if row is not None else None

    async def page(
        self,
        *,
        search: str | None,
        is_admin: bool | None,
        deactivated: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MemberSummary], int]:
        statement = members_statement(search=search, is_admin=is_admin, deactivated=deactivated)
        counted = _member_filters(
            select(func.count()).select_from(UserRow),
            search=search,
            is_admin=is_admin,
            deactivated=deactivated,
        )
        rows, total = await page_of(self._session, statement, limit, offset, count=counted)
        return [_summary(row) for row in rows], total

    async def set_deactivated(self, member_id: int, *, at: datetime, on: bool) -> bool:
        was = UserRow.deactivated_at.is_(None) if on else UserRow.deactivated_at.is_not(None)
        statement = (
            update(UserRow)
            .where(UserRow.id == member_id, was)
            .values(deactivated_at=naive_utc(at) if on else None)
        )
        changed = cast("CursorResult[Any]", await self._session.execute(statement))
        return _changed(changed) > 0

    async def end_sessions(self, member_id: int, *, at: datetime) -> int:
        statement = (
            update(RefreshTokenRow)
            .where(
                RefreshTokenRow.user_id == member_id,
                RefreshTokenRow.revoked_at.is_(None),
                RefreshTokenRow.expires_at > naive_utc(at),
            )
            .values(revoked_at=naive_utc(at))
        )
        ended = cast("CursorResult[Any]", await self._session.execute(statement))
        return _changed(ended)


# The three questions `Invite.state` answers about one invite, asked of the table. A
# spent invite that was revoked afterwards counts as revoked there, so it does here too.
_INVITE_STATES = {
    "open": and_(InviteRow.used_at.is_(None), InviteRow.revoked_at.is_(None)),
    "used": and_(InviteRow.used_at.is_not(None), InviteRow.revoked_at.is_(None)),
    "revoked": InviteRow.revoked_at.is_not(None),
}


class SqlAlchemyInvitationRepository(InvitationRepository):
    """Invites, read and written through the moderation transaction.

    The invites table belongs to the auth context and this is the one place outside it
    that reads it: an invite is issued by an admin and spent by a signup, and there is no
    copy of the row in between for the two of them to disagree about.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, invite_id: int) -> Invite | None:
        row = await self._session.get(InviteRow, invite_id)
        return row.to_entity() if row is not None else None

    async def add(self, invite: Invite) -> None:
        # Same shape as the auth repository's: the row number only exists once the insert
        # has run, and the invite that comes back has to carry it, or the admin who just
        # made one is handed a token with no id to revoke it with.
        row = await self._session.merge(InviteRow.from_entity(invite))
        await self._session.flush()
        invite.id = row.id

    async def page(self, *, state: str | None, limit: int, offset: int) -> tuple[list[Invite], int]:
        statement = select(InviteRow)
        if state is not None:
            statement = statement.where(_INVITE_STATES[state])
        statement = statement.order_by(InviteRow.created_at.desc(), InviteRow.id.desc())
        rows, total = await page_of(self._session, statement, limit, offset)
        return [row[0].to_entity() for row in rows], total

    async def revoke(self, invite: Invite, *, at: datetime) -> bool:
        statement = (
            update(InviteRow)
            .where(
                InviteRow.id == invite.require_id(),
                InviteRow.used_at.is_(None),
                InviteRow.revoked_at.is_(None),
            )
            .values(revoked_at=naive_utc(at))
        )
        closed = cast("CursorResult[Any]", await self._session.execute(statement))
        return _changed(closed) > 0
