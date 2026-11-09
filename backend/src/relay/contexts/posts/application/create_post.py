"""Writing a post down."""

from uuid import UUID

from relay.contexts.posts.application.unit_of_work import PostsUnitOfWork
from relay.contexts.posts.domain.ports import CellStandard, LiveFeed, NoLiveFeed
from relay.contexts.posts.domain.post import Post, PostNotFoundError
from relay.shared.application import Clock


class CreatePost:
    """Says a post and saves it. The clock is injected so a test knows when it was said."""

    def __init__(
        self,
        uow: PostsUnitOfWork,
        clock: Clock,
        cells: CellStandard,
        live_feed: LiveFeed | None = None,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._cells = cells
        # Optional, because a post is a post whether or not anyone is out there reading
        # one at this moment.
        self._live_feed = live_feed or NoLiveFeed()

    async def execute(
        self,
        *,
        author_id: UUID,
        body: str,
        location_cell: str | None = None,
        community_id: UUID | None = None,
        parent_id: UUID | None = None,
    ) -> Post:
        said_in = self._filed_under(location_cell)
        async with self._uow:
            parent = None
            if parent_id is not None:
                # A reply to a post that is not there answers nothing, and no thread will
                # ever show it, so it is refused here rather than filed as an orphan.
                parent = await self._uow.posts.get(parent_id)
                if parent is None or not parent.is_up:
                    raise PostNotFoundError(f"No post {parent_id} to reply to.")
            if parent is not None:
                post = Post.reply_to(
                    parent,
                    author_id=author_id,
                    body=body,
                    created_at=self._clock.now(),
                    location_cell=said_in,
                    community_id=community_id,
                )
            else:
                post = Post.write(
                    author_id=author_id,
                    body=body,
                    created_at=self._clock.now(),
                    location_cell=said_in,
                    community_id=community_id,
                    parent_id=parent_id,
                )
            await self._uow.posts.add(post)
            await self._uow.commit()
        # Outside the transaction, so a post that was never saved is never announced, and
        # with nothing awaited between the commit and here, so nobody is ever told about a
        # post before it is in the database and can be read back.
        self._live_feed.announce(post)
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
