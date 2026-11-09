"""The queue: posts by status, newest first, with the total so it can say how long it is."""

from typing import NamedTuple
from uuid import UUID

from relay.contexts.admin.application.unit_of_work import ModerationUnitOfWork
from relay.contexts.posts.domain.post import ModerationStatus, Post


class QueuePage(NamedTuple):
    """One page of the queue, and what a machine already thought about each of them."""

    posts: list[Post]
    total: int
    ai_decisions: dict[UUID, dict]


class ModerationQueue:
    """Read the queue.

    Offset paging rather than the cursor the public feed uses. Someone scrolling a feed
    backwards wants a cursor; someone working through a queue wants to know there are
    forty-one left, and to be able to come back to the third page of them.

    `ai_decisions` is keyed by post id and only holds the posts a model has actually
    looked at. A post missing from it has no opinion attached, which is a different fact
    from an opinion that said nothing was wrong.
    """

    def __init__(self, uow: ModerationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self, *, status: ModerationStatus | None, limit: int, offset: int
    ) -> QueuePage:
        """Posts newest first, how many there are under that status, and the machine's say."""
        async with self._uow:
            posts, total = await self._uow.posts.page(status=status, limit=limit, offset=offset)
            decisions = await self._uow.log.ai_decisions([post.id for post in posts])
            return QueuePage(posts=posts, total=total, ai_decisions=decisions)
