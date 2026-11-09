"""The replies under one post, oldest first."""

from uuid import UUID

from relay.contexts.posts.application.unit_of_work import PostsUnitOfWork
from relay.contexts.posts.domain.post import Post, PostNotFoundError


class GetReplies:
    """The posts said in reply to a post, and no deeper.

    One level only: a reply to a reply is another call away, which is what lets the
    client open a thread one step at a time or all at once. The post itself has to
    still be up - a thread under a post moderation took down is not shown either.
    """

    def __init__(self, uow: PostsUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, post_id: UUID) -> list[Post]:
        async with self._uow:
            post = await self._uow.posts.get(post_id)
            if post is None or not post.is_up:
                raise PostNotFoundError(f"No post {post_id} to reply to.")
            return await self._uow.posts.replies_to(post_id)
