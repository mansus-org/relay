"""Reading a community's feed out of the posts table."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relay.contexts.communities.domain.ports import CommunityFeedReader
from relay.contexts.posts.domain.post import ModerationStatus, Post
from relay.contexts.posts.infrastructure.models import PostModel


class SqlAlchemyCommunityFeedReader(CommunityFeedReader):
    """A community's posts, read straight off the posts table.

    The posts context owns that table and this only reads it: a post is filed into a
    community when it is created, and by the time anyone asks for a feed the rows are
    already there. Reading it here rather than teaching posts about communities keeps
    the dependency pointing the one way it already does — communities needs posts,
    posts never needs communities.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def page(
        self, *, community_id: UUID, before: datetime | None, limit: int
    ) -> Sequence[Post]:
        statement = (
            select(PostModel)
            .where(PostModel.community_id == community_id)
            .where(PostModel.moderation_status != ModerationStatus.REMOVED.value)
            .order_by(PostModel.created_at.desc())
            .limit(limit)
        )
        if before is not None:
            # Compared in UTC, the one zone the column is written in, whichever zone the
            # cursor was made in.
            statement = statement.where(PostModel.created_at < before.astimezone(UTC))
        rows = (await self._session.execute(statement)).scalars()
        return [row.to_domain() for row in rows]
