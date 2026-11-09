"""A page of a community's feed: its members' posts, and who said each one."""

from relay.contexts.posts.domain.feed import Cursor
from relay.contexts.posts.domain.post import Post
from relay.shared.domain import ValueObject


class CommunityPost(ValueObject):
    """One post as a community shows it.

    `pseudonym` is the name its author goes by in this community, when they chose one.
    Deciding what to print instead — the placeholder the accounts context will replace
    — is the HTTP layer's business, so only the choice is carried here.
    """

    post: Post
    pseudonym: str | None = None


class CommunityFeedPage(ValueObject):
    """Newest first, and where to ask for the older ones.

    A page of its own rather than posts' `FeedPage`, because a community's posts are
    posts plus what this community calls each of their authors.
    """

    posts: tuple[CommunityPost, ...]
    next_cursor: Cursor | None = None
