"""Writing a post down."""

from uuid import UUID

from relay.contexts.posts.application.unit_of_work import PostsUnitOfWork
from relay.contexts.posts.domain.post import Post
from relay.shared.application import Clock


class CreatePost:
    """Says a post and saves it. The clock is injected so a test knows when it was said."""

    def __init__(self, uow: PostsUnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(
        self,
        *,
        author_id: UUID,
        body: str,
        location_cell: str | None = None,
        community_id: UUID | None = None,
    ) -> Post:
        post = Post.write(
            author_id=author_id,
            body=body,
            created_at=self._clock.now(),
            location_cell=location_cell,
            community_id=community_id,
        )
        async with self._uow:
            await self._uow.posts.add(post)
            await self._uow.commit()
        return post
