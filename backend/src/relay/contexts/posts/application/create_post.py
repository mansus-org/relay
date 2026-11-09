"""Writing a post down."""

from uuid import UUID

from relay.contexts.posts.application.unit_of_work import PostsUnitOfWork
from relay.contexts.posts.domain.ports import CellStandard
from relay.contexts.posts.domain.post import Post
from relay.shared.application import Clock


class CreatePost:
    """Says a post and saves it. The clock is injected so a test knows when it was said."""

    def __init__(self, uow: PostsUnitOfWork, clock: Clock, cells: CellStandard) -> None:
        self._uow = uow
        self._clock = clock
        self._cells = cells

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
            location_cell=self._filed_under(location_cell),
            community_id=community_id,
        )
        async with self._uow:
            await self._uow.posts.add(post)
            await self._uow.commit()
        return post

    def _filed_under(self, cell: str | None) -> str | None:
        """Where it was said, in the form the feed reads back.

        Nothing is filed under a string no feed will ever ask for: a post saved as
        `883920CD1BFFFFF`, or at the wrong resolution, is a post its author will never
        see again. Refusing that write is kinder than a 201 and silence. No cell at all
        stays allowed, because that is a writer choosing not to say where they are.
        """
        named = cell.strip() if cell else ""
        return self._cells.normalise(named) if named else None
