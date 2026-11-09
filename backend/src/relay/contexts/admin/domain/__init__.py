"""Moderation domain: the decisions, what they are allowed to be, and what they leave behind."""

from relay.contexts.admin.domain.errors import (
    AlreadyInThatStateError,
    InviteNotFoundError,
    MemberCannotBeDeactivatedError,
    MemberNotFoundError,
)
from relay.contexts.admin.domain.members import MemberSummary, can_deactivate
from relay.contexts.admin.domain.moderation_log import (
    MAX_REASON_LENGTH,
    ModerationAction,
    ModerationLog,
)
from relay.contexts.admin.domain.ports import (
    InvitationRepository,
    MemberRepository,
    ModeratedPostRepository,
    ModerationLogRepository,
)
from relay.contexts.admin.domain.review import ReviewAction, ReviewRule, rule_for

__all__ = [
    "MAX_REASON_LENGTH",
    "AlreadyInThatStateError",
    "InvitationRepository",
    "InviteNotFoundError",
    "MemberCannotBeDeactivatedError",
    "MemberNotFoundError",
    "MemberRepository",
    "MemberSummary",
    "ModeratedPostRepository",
    "ModerationAction",
    "ModerationLog",
    "ModerationLogRepository",
    "ReviewAction",
    "ReviewRule",
    "can_deactivate",
    "rule_for",
]
