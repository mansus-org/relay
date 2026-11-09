"""Reacting to a post."""

from uuid import UUID

from relay.contexts.posts.application.unit_of_work import PostsUnitOfWork
from relay.contexts.posts.domain.post import PostNotFoundError
from relay.contexts.posts.domain.reaction import AlreadyReactedError, Reaction, ReactionTally
from relay.shared.application import Clock


class AddReaction:
    """Puts the reader's emoji on a post and answers what that emoji now counts.

    One person, one emoji, once: the same emoji twice from the same person is refused,
    because it is the same opinion said twice and not two of them. A second, different
    emoji is allowed - that is a different thing said.
    """

    def __init__(self, uow: PostsUnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, *, post_id: UUID, user_id: UUID, emoji: str) -> ReactionTally:
        reaction = Reaction.given(
            post_id=post_id, user_id=user_id, emoji=emoji, created_at=self._clock.now()
        )
        async with self._uow:
            post = await self._uow.posts.get(post_id)
            if post is None or not post.is_up:
                raise PostNotFoundError(f"No post {post_id} to react to.")
            left = await self._uow.reactions.get(
                post_id=post_id, user_id=user_id, emoji=reaction.emoji
            )
            if left is not None:
                raise AlreadyReactedError(f"You have already reacted with {reaction.emoji}.")
            await self._uow.reactions.add(reaction)
            await self._uow.commit()
            counted = await self._uow.reactions.tallies([post_id], viewer=user_id)
        return next(tally for tally in counted[post_id] if tally.emoji == reaction.emoji)
