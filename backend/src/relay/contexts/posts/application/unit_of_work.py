"""The posts unit of work: one transaction over posts and what people left on them."""

from relay.contexts.posts.domain.ports import PostRepository, ReactionRepository
from relay.shared.application import UnitOfWork


class PostsUnitOfWork(UnitOfWork):
    """A transaction reaching the posts table and the reactions on it.

    Implementations set `posts` and `reactions` on entry, so one commit writes both
    or neither.
    """

    posts: PostRepository
    reactions: ReactionRepository
