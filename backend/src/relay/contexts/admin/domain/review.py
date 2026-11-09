"""What moderation may do to a post, and what it leaves behind.

The table at the bottom of this file is the whole rule. Each action names the state it
leaves a post in and the states it is allowed to come from, so there is one place to
look when someone asks why restoring a post that was never removed is refused.

Nothing here decides whether a post can be read: Relay shows everything that has not
been removed, so approving is a mark that somebody looked, and removing is the only
gate there is.
"""

from enum import StrEnum
from typing import NamedTuple

from relay.contexts.admin.domain.errors import AlreadyInThatStateError
from relay.contexts.admin.domain.moderation_log import ModerationAction
from relay.contexts.posts.domain.post import ModerationStatus, Post


class ReviewAction(StrEnum):
    """The three things somebody in charge can ask to do to a post."""

    APPROVE = "approve"
    REMOVE = "remove"
    RESTORE = "restore"


class ReviewRule(NamedTuple):
    """One action: where it applies from, where it leaves the post, and how it is logged."""

    action: ReviewAction
    leaves: ModerationStatus
    only_from: frozenset[ModerationStatus]
    logged_as: ModerationAction

    def apply(self, post: Post) -> Post:
        """This post as the action leaves it, or a refusal saying what it currently is.

        Approving a post that is already approved is not a mistake somebody makes by
        accident, it is a second click on a card they could not tell had been dealt
        with. So it answers with the state rather than an apology, and writes nothing.
        """
        current = post.moderation_status
        if current not in self.only_from:
            if current is self.leaves:
                raise AlreadyInThatStateError(f"That post is already {current.value}.")
            raise AlreadyInThatStateError(
                f"That post is {current.value}, so it cannot be {self.action.value}d."
            )
        if self.leaves is ModerationStatus.REMOVED:
            # The posts context owns what removal means; this only asks for it.
            return post.removed()
        return post.model_copy(update={"moderation_status": self.leaves})


_RULES: dict[ReviewAction, ReviewRule] = {
    ReviewAction.APPROVE: ReviewRule(
        ReviewAction.APPROVE,
        ModerationStatus.APPROVED,
        frozenset({ModerationStatus.PENDING}),
        ModerationAction.APPROVED,
    ),
    ReviewAction.REMOVE: ReviewRule(
        ReviewAction.REMOVE,
        ModerationStatus.REMOVED,
        frozenset({ModerationStatus.PENDING, ModerationStatus.APPROVED}),
        ModerationAction.REMOVED,
    ),
    ReviewAction.RESTORE: ReviewRule(
        ReviewAction.RESTORE,
        ModerationStatus.APPROVED,
        frozenset({ModerationStatus.REMOVED}),
        ModerationAction.RESTORED,
    ),
}


def rule_for(action: ReviewAction) -> ReviewRule:
    """The rule for an action. Every action has exactly one."""
    return _RULES[action]
