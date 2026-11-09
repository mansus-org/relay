"""One post, whatever its status - including the ones a reader can no longer see."""

from typing import NamedTuple
from uuid import UUID

from relay.contexts.admin.application.unit_of_work import ModerationUnitOfWork
from relay.contexts.posts.domain.post import Post


class ModeratedPost(NamedTuple):
    """One post, and the machine's opinion about it if anything ever formed one."""

    post: Post
    ai_decision: dict | None


class ReadPost:
    """Look one post up in full.

    The public endpoint cannot do this: it only ever returns posts that are still up,
    which is the right rule for a reader and a wall for an admin looking into something
    that was taken down last week.
    """

    def __init__(self, uow: ModerationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, *, post_id: UUID) -> ModeratedPost:
        async with self._uow:
            post = await self._uow.posts.get(post_id)
            decisions = await self._uow.log.ai_decisions([post_id])
            return ModeratedPost(post=post, ai_decision=decisions.get(post_id))
