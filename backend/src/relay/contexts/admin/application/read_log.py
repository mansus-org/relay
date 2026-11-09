"""Read the trail: what moderation did, newest first, narrowed by whatever is asked."""

from uuid import UUID

from relay.contexts.admin.application.unit_of_work import ModerationUnitOfWork
from relay.contexts.admin.domain.moderation_log import ModerationLog


class ReadModerationLog:
    """The audit trail, for the person who has to answer for a decision.

    Every filter is optional and they combine, because the question is never the same
    twice: what happened to this post, what has this account had done to it, what has
    this admin been doing, what happened in this community.
    """

    def __init__(self, uow: ModerationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        post_id: UUID | None = None,
        community_id: UUID | None = None,
        target_user_id: int | None = None,
        actor_id: int | None = None,
        limit: int,
        offset: int,
    ) -> tuple[list[ModerationLog], int]:
        async with self._uow:
            return await self._uow.log.page(
                post_id=post_id,
                community_id=community_id,
                target_user_id=target_user_id,
                actor_id=actor_id,
                limit=limit,
                offset=offset,
            )
