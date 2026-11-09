"""The communities and members repositories: statements over those two tables."""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Select, false, func, select
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from relay.contexts.communities.domain.community import Community
from relay.contexts.communities.domain.membership import Membership
from relay.contexts.communities.domain.ports import (
    CommunityRepository,
    MembershipRepository,
)
from relay.contexts.communities.infrastructure.models import (
    CommunityMemberModel,
    CommunityModel,
)
from relay.shared.domain import ConflictError


def counted(*, viewer: UUID | None) -> tuple[ColumnElement, ColumnElement]:
    """How many members a community has, and whether `viewer` is one of them.

    Two correlated subqueries rather than a join and a GROUP BY, so a community with no
    members still comes back — as 0, which is the answer — instead of vanishing from
    the list for having none.
    """
    members = (
        select(func.count())
        .select_from(CommunityMemberModel)
        .where(CommunityMemberModel.community_id == CommunityModel.id)
        .correlate(CommunityModel)
        .scalar_subquery()
        .label("member_count")
    )
    mine = (
        false()
        if viewer is None
        else select(1)
        .where(CommunityMemberModel.community_id == CommunityModel.id)
        .where(CommunityMemberModel.user_id == viewer)
        .correlate(CommunityModel)
        .exists()
    ).label("is_member")
    return members, mine


def anchored_statement(*, viewer: UUID | None) -> Select:
    """Every community with somewhere to be, newest first, counted for `viewer`.

    Communities with no locality are left out here rather than filtered out later:
    they are a different thing, and the screen this feeds is a list of places.
    """
    members, mine = counted(viewer=viewer)
    return (
        select(CommunityModel, members, mine)
        .where(CommunityModel.location_cell.is_not(None))
        .where(CommunityModel.radius_km.is_not(None))
        .order_by(CommunityModel.created_at.desc())
    )


class SqlAlchemyCommunityRepository(CommunityRepository):
    """Communities in the session its unit of work handed over."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: UUID) -> Community | None:
        row = await self._session.get(CommunityModel, id)
        return row.to_domain() if row is not None else None

    async def get_for(self, id: UUID, *, viewer: UUID | None) -> Community | None:
        members, mine = counted(viewer=viewer)
        statement = select(CommunityModel, members, mine).where(CommunityModel.id == id)
        found = (await self._session.execute(statement)).first()
        return _one(found) if found is not None else None

    async def list_anchored(self, *, viewer: UUID | None) -> list[Community]:
        rows = (await self._session.execute(anchored_statement(viewer=viewer))).all()
        return [_one(row) for row in rows]

    async def slug_taken(self, slug: str) -> bool:
        statement = select(CommunityModel.id).where(CommunityModel.slug == slug).limit(1)
        return (await self._session.execute(statement)).first() is not None

    async def add(self, entity: Community) -> None:
        self._session.add(CommunityModel.from_domain(entity))
        # Flushed here, so the unique slug is caught while this session can still say
        # so: a second "Book Club" is refused by the use case one query earlier, and
        # what gets through is two requests that raced each other for the same slug.
        try:
            await self._session.flush()
        except IntegrityError as error:
            raise ConflictError(f"Something already answers to {entity.slug}.") from error


class SqlAlchemyMembershipRepository(MembershipRepository):
    """Memberships in the session its unit of work handed over."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: UUID) -> Membership | None:
        row = await self._session.get(CommunityMemberModel, id)
        return row.to_domain() if row is not None else None

    async def find(self, *, community_id: UUID, user_id: UUID) -> Membership | None:
        statement = (
            select(CommunityMemberModel)
            .where(CommunityMemberModel.community_id == community_id)
            .where(CommunityMemberModel.user_id == user_id)
            .limit(1)
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def pseudonyms(self, *, community_id: UUID, user_ids: Iterable[UUID]) -> dict[UUID, str]:
        wanted = list(user_ids)
        if not wanted:
            return {}
        statement = (
            select(CommunityMemberModel.user_id, CommunityMemberModel.pseudonym)
            .where(CommunityMemberModel.community_id == community_id)
            .where(CommunityMemberModel.user_id.in_(wanted))
            .where(CommunityMemberModel.pseudonym.is_not(None))
        )
        rows = (await self._session.execute(statement)).all()
        return {row.user_id: row.pseudonym for row in rows if row.pseudonym}

    async def add(self, entity: Membership) -> None:
        self._session.add(CommunityMemberModel.from_domain(entity))
        try:
            await self._session.flush()
        except IntegrityError as error:
            # One person is one membership of a community. `JoinCommunity` looks for
            # it first, so this only happens when two joins raced; the second one has
            # failed to add anything and says so.
            raise ConflictError(f"Already a member of community {entity.community_id}.") from error


def _one(row: Row) -> Community:
    """One row of `select(CommunityModel, count, is_member)`, as a community."""
    model, member_count, is_member = row
    return model.to_domain(member_count=int(member_count), is_member=bool(is_member))
