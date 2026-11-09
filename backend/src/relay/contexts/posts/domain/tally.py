"""What has been put on a post by everyone else: the reactions, and how many replies."""

from relay.contexts.posts.domain.reaction import ReactionTally
from relay.shared.domain import ValueObject


class PostTally(ValueObject):
    """The answer to "what do people say about this post?", for one post.

    A read model, like `FeedPage`: nothing writes it, everything that shows a post
    reads it, and a post nobody has reacted to or replied to has an empty one.
    """

    reactions: tuple[ReactionTally, ...] = ()
    reply_count: int = 0
