"""One decision about one post, and the line that records it."""

from uuid import UUID

from relay.contexts.admin.application.unit_of_work import ModerationUnitOfWork
from relay.contexts.admin.domain.errors import AlreadyInThatStateError
from relay.contexts.admin.domain.moderation_log import ModerationLog
from relay.contexts.admin.domain.review import ReviewAction, rule_for
from relay.contexts.posts.domain.post import Post
from relay.shared.application import Clock


class ReviewPost:
    """Approve, remove or restore a post, and write down that you did.

    One use case for all three, because they are the same shape: a rule, a compare-and-
    set, a log line. Three classes would be three places to keep the log line identical,
    and a decision that goes unwritten is the exact thing this exists to stop.
    """

    def __init__(self, uow: ModerationUnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(
        self, *, post_id: UUID, action: ReviewAction, reason: str, admin_id: int
    ) -> Post:
        rule = rule_for(action)
        async with self._uow:
            post = await self._uow.posts.get(post_id)
            decided = rule.apply(post)
            moved = await self._uow.posts.set_status(
                decided, to=rule.leaves, was=post.moderation_status
            )
            if not moved:
                # Somebody else decided this between the read above and this write. The
                # decision stands, it just was not made by this click, so the answer is
                # the state and not a second line in the trail for it.
                raise AlreadyInThatStateError(
                    "That post was decided on by someone else while this was in flight."
                )
            await self._uow.log.add(
                ModerationLog.for_post(
                    actor_id=admin_id,
                    action=rule.logged_as,
                    post=decided,
                    reason=reason,
                    created_at=self._clock.now(),
                )
            )
            await self._uow.commit()
            return decided
