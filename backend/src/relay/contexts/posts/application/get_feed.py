"""One page of a locality feed: the newest posts said within a radius of where you are."""

from relay.contexts.posts.application.unit_of_work import PostsUnitOfWork
from relay.contexts.posts.domain.cells import DEFAULT_RADIUS_KM
from relay.contexts.posts.domain.feed import Cursor, FeedPage
from relay.contexts.posts.domain.ports import CellNeighbourhood


class GetFeed:
    """Reads the neighbourhood's feed, newest first, a page at a time.

    The locality filter is the cell and the radius and nothing else: a post said
    outside the ring, or with no cell at all, is not in this feed, and a removed post
    is in no feed.
    """

    #: The page size mobile asks for (PAGE_SIZE in mobile/src/domain/post.ts).
    PAGE_SIZE = 20

    def __init__(self, uow: PostsUnitOfWork, neighbourhood: CellNeighbourhood) -> None:
        self._uow = uow
        self._neighbourhood = neighbourhood

    async def execute(
        self, *, cell: str, radius_km: float = DEFAULT_RADIUS_KM, cursor: Cursor | None = None
    ) -> FeedPage:
        cells = self._neighbourhood.visible_from(cell, radius_km)
        before = cursor.value if cursor is not None else None
        async with self._uow:
            found = await self._uow.posts.page_neighbouring(
                cells=cells, before=before, limit=self.PAGE_SIZE + 1
            )
        # One extra read tells us whether there is more without a second query.
        more = len(found) > self.PAGE_SIZE
        posts = found[: self.PAGE_SIZE]
        return FeedPage(
            posts=tuple(posts),
            next_cursor=Cursor(value=posts[-1].created_at) if more and posts else None,
        )
