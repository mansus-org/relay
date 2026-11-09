"""The moderation unit of work: one transaction over everything an admin can touch."""

from relay.contexts.admin.domain.ports import (
    InvitationRepository,
    MemberRepository,
    ModeratedPostRepository,
    ModerationLogRepository,
)
from relay.shared.application import UnitOfWork


class ModerationUnitOfWork(UnitOfWork):
    """A transaction reaching the queue, the trail, the members and the invites.

    Implementations set the four repositories on entry, so one commit writes a decision
    and its log line together. That pairing is the point: a moderation nobody wrote down
    is a moderation nobody can be asked about afterwards, and two transactions is the
    gap where the line gets lost.
    """

    posts: ModeratedPostRepository
    log: ModerationLogRepository
    members: MemberRepository
    invites: InvitationRepository
