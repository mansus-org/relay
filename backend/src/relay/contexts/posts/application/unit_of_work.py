"""The posts unit of work: one transaction that can reach the posts table."""

from relay.contexts.posts.domain.ports import PostRepository
from relay.shared.application import UnitOfWork


class PostsUnitOfWork(UnitOfWork):
    """A transaction over the posts table. Implementations set `posts` on entry."""

    posts: PostRepository
