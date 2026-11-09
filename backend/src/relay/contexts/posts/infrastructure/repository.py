"""The posts repository: SQLAlchemy statements over the posts table."""

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from relay.contexts.posts.domain.ports import PostRepository
from relay.contexts.posts.domain.post import ModerationStatus, Post
from relay.contexts.posts.infrastructure.models import PostModel


def feed_statement(cells: list[str], before: datetime | None, limit: int) -> Select:
    """One page of a locality feed, newest first.

    `IN` leaves out the posts that named no locality at all, which is what keeps them
    out of every locality feed. Built here rather than inline so the query the
    repository runs is the query a test can put under EXPLAIN.
    """
    statement = (
        select(PostModel)
        .where(PostModel.location_cell.in_(cells))
        .where(PostModel.moderation_status != ModerationStatus.REMOVED.value)
        .order_by(PostModel.created_at.desc())
        .limit(limit)
    )
    if before is not None:
        # Compared in UTC, the one zone the column is written in. SQLite keeps no offset
        # of its own, so a page asked for from another zone would otherwise be read as
        # that zone's wall clock and start at the wrong instant.
        statement = statement.where(PostModel.created_at < before.astimezone(UTC))
    return statement


class SqlAlchemyPostRepository(PostRepository):
    """Posts in the same session as the unit of work that handed it over."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: UUID) -> Post | None:
        row = await self._session.get(PostModel, id)
        return row.to_domain() if row is not None else None

    async def add(self, entity: Post) -> None:
        self._session.add(PostModel.from_domain(entity))

    async def page_neighbouring(
        self, *, cells: Iterable[str], before: datetime | None, limit: int
    ) -> list[Post]:
        statement = feed_statement(list(cells), before, limit)
        rows = (await self._session.execute(statement)).scalars()
        return [row.to_domain() for row in rows]
