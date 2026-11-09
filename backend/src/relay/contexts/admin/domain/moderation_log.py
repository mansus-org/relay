"""The record of what moderation did: who acted, on what, and what they said why."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from relay.contexts.admin.domain.members import MemberSummary
from relay.contexts.auth.domain.models import RelationalEntity
from relay.contexts.posts.domain.post import Post
from relay.shared.domain import ValidationError

# Long enough to explain a call in a sentence or two. A removal reason gets read by
# the person it was done to, so it is a sentence, not a filing note.
MAX_REASON_LENGTH = 500


class ModerationAction(StrEnum):
    """What was done. A closed list: anything else is a bug, not a new kind of decision."""

    APPROVED = "approved"
    REMOVED = "removed"
    RESTORED = "restored"
    FLAGGED = "flagged"
    MEMBER_DEACTIVATED = "member_deactivated"
    MEMBER_RESTORED = "member_restored"


class ModerationTrigger(StrEnum):
    """Who made the call. `human` is somebody with the job, `ai` is the machine.

    The two of them end up in the same table because a queue is read best as one story:
    what the machine thought, and what the person standing behind it decided.
    """

    HUMAN = "human"
    AI = "ai"


# The actions that take something away from somebody, and so travel with a reason.
# Both of them are things a person will be asked about later, by the person they happened
# to. What puts a thing back is not on the list: restoring needs no defence.
_REASONS_REQUIRED = frozenset({ModerationAction.REMOVED, ModerationAction.MEMBER_DEACTIVATED})


def _reason(action: "ModerationAction", raw: str) -> str:
    """Trim a reason and check it is one this kind of action can stand behind."""
    said = (raw or "").strip()
    if len(said) > MAX_REASON_LENGTH:
        raise ValidationError(f"A moderation reason is at most {MAX_REASON_LENGTH} characters.")
    if not said and action in _REASONS_REQUIRED:
        # Taking something away from a person without a why is an admin nobody can hold
        # to anything, and the one who asks for the reason is usually the one it was done
        # to. "It was removed" is not a reason; it is the decision again, louder.
        raise ValidationError(f"{action.value} needs a reason: someone will ask for it.")
    return said


class ModerationLog(RelationalEntity):
    """One decision, written down.

    Append-only. A row is not a setting that happens to be true now, it is something
    that happened, which is why nothing in Relay updates or deletes one.
    """

    actor_id: int | None
    action: ModerationAction
    created_at: datetime
    trigger: ModerationTrigger = ModerationTrigger.HUMAN
    post_id: UUID | None = None
    community_id: UUID | None = None
    target_user_id: int | None = None
    reason: str = ""
    ai_decision: dict | None = None

    @classmethod
    def for_post(
        cls,
        *,
        actor_id: int,
        action: ModerationAction,
        post: Post,
        reason: str,
        created_at: datetime,
    ) -> "ModerationLog":
        """A decision about one post, made by a person.

        The post is named by id and not copied: what it says now is not what it said
        then, and this row is about the moment it was decided, not the text itself.
        """
        return cls(
            actor_id=actor_id,
            action=action,
            post_id=post.id,
            community_id=post.community_id,
            reason=_reason(action, reason),
            created_at=created_at,
        )

    @classmethod
    def flagged_by_machine(
        cls, *, post: Post, decision: dict, created_at: datetime
    ) -> "ModerationLog":
        """What a machine decided about a post, and left for a person to finish.

        No actor: a model has no account and no name, and inventing one to fill a column
        would be the first lie in a table whose whole job is telling the truth. The
        verdict goes in `ai_decision` as it came out, and the queue shows it beside the
        post, so the admin reads the opinion and the post together.
        """
        return cls(
            actor_id=None,
            action=ModerationAction.FLAGGED,
            trigger=ModerationTrigger.AI,
            post_id=post.id,
            community_id=post.community_id,
            ai_decision=decision,
            created_at=created_at,
        )

    @classmethod
    def for_member(
        cls,
        *,
        actor_id: int,
        action: ModerationAction,
        member: MemberSummary,
        reason: str,
        created_at: datetime,
    ) -> "ModerationLog":
        """A decision about an account.

        Only switching one off and putting it back is logged. Being made an admin is an
        operator's act at a database prompt with no request behind it, so there would be
        no actor to write down.
        """
        return cls(
            actor_id=actor_id,
            action=action,
            target_user_id=member.id,
            reason=_reason(action, reason),
            created_at=created_at,
        )
