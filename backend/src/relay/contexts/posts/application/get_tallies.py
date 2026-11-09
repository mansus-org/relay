"""What people have left on posts: their reactions, and how many replies."""

from collections.abc import Sequence
from uuid import UUID

from relay.contexts.posts.application.unit_of_work import PostsUnitOfWork
from relay.contexts.posts.domain.tally import PostTally


class GetTallies:
    """Counts what sits under a list of posts, for the reader asking.

    A feed of twenty posts is counted twice - once for the reactions, once for the
    replies - and not twenty times over. `viewer` is who is reading, so their own
    reactions come back marked; nobody named is a public read and nothing is marked.
    """

    def __init__(self, uow: PostsUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self, post_ids: Sequence[UUID], *, viewer: UUID | None = None
    ) -> dict[UUID, PostTally]:
        asked = list(dict.fromkeys(post_ids))
        async with self._uow:
            reactions = await self._uow.reactions.tallies(asked, viewer=viewer)
            replies = await self._uow.posts.count_replies(asked)
        return {
            post_id: PostTally(reactions=reactions[post_id], reply_count=replies[post_id])
            for post_id in asked
        }
