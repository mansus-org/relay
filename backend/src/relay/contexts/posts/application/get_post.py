"""One post on its own, for a deep link or a notification."""

from uuid import UUID

from relay.contexts.posts.application.unit_of_work import PostsUnitOfWork
from relay.contexts.posts.domain.post import ModerationStatus, Post, PostNotFoundError


class GetPost:
    """Fetches a post by id. A removed one is treated as gone, the way a feed treats it."""

    def __init__(self, uow: PostsUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, post_id: UUID) -> Post:
        async with self._uow:
            post = await self._uow.posts.get(post_id)
        if post is None or post.moderation_status is ModerationStatus.REMOVED:
            raise PostNotFoundError(f"No post {post_id} to show.")
        return post
