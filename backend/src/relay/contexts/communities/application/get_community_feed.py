"""One page of a community's feed: what its members have said, newest first."""

from uuid import UUID

from relay.contexts.communities.application.unit_of_work import CommunitiesUnitOfWork
from relay.contexts.communities.domain.community import CommunityNotFoundError
from relay.contexts.communities.domain.feed import CommunityFeedPage, CommunityPost
from relay.contexts.communities.domain.membership import NotAMemberError
from relay.contexts.posts.domain.feed import Cursor


class GetCommunityFeed:
    """Reads a community's feed, for its members only.

    Membership is the whole gate. A community's posts are what its members said to
    each other, and a nearby list that handed out every community's contents to anyone
    who guessed an id would make joining pointless.
    """

    #: The page size mobile asks for (PAGE_SIZE in mobile/src/domain/post.ts), which is
    #: the same one the locality feed pages by, so the two screens scroll alike.
    PAGE_SIZE = 20

    def __init__(self, uow: CommunitiesUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        community_id: UUID,
        viewer: UUID | None = None,
        cursor: Cursor | None = None,
    ) -> CommunityFeedPage:
        async with self._uow:
            if await self._uow.communities.get(community_id) is None:
                raise CommunityNotFoundError(f"No community {community_id} to read.")
            member = (
                None
                if viewer is None
                else await self._uow.members.find(community_id=community_id, user_id=viewer)
            )
            if member is None:
                raise NotAMemberError(f"Only members of community {community_id} read its feed.")
            found = await self._uow.feed.page(
                community_id=community_id,
                before=cursor.value if cursor is not None else None,
                limit=self.PAGE_SIZE + 1,
            )
            called = await self._uow.members.pseudonyms(
                community_id=community_id, user_ids={post.author_id for post in found}
            )
        # One extra read tells us whether there is more without a second query.
        more = len(found) > self.PAGE_SIZE
        posts = list(found)[: self.PAGE_SIZE]
        return CommunityFeedPage(
            posts=tuple(
                CommunityPost(post=post, pseudonym=called.get(post.author_id)) for post in posts
            ),
            next_cursor=Cursor(value=posts[-1].created_at) if more and posts else None,
        )
