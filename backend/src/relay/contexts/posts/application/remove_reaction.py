"""Taking a reaction back."""

from uuid import UUID

from relay.contexts.posts.application.unit_of_work import PostsUnitOfWork
from relay.contexts.posts.domain.reaction import ReactionNotFoundError, as_one_emoji


class RemoveReaction:
    """Takes the reader's emoji off a post.

    Taking back a reaction you never left is reported, not ignored: it means the
    screen you are looking at is showing something that is not there.
    """

    def __init__(self, uow: PostsUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, *, post_id: UUID, user_id: UUID, emoji: str) -> None:
        # Counted the same way it was put on, or a heart typed on another phone would
        # be a reaction nobody can take back.
        named = as_one_emoji(emoji.strip())
        async with self._uow:
            taken = await self._uow.reactions.remove(post_id=post_id, user_id=user_id, emoji=named)
            if not taken:
                raise ReactionNotFoundError(f"You have not reacted with {named}.")
            await self._uow.commit()
