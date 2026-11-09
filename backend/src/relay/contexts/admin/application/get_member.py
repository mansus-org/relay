"""One account in full: what it is, what it has made, and what has been done to it."""

from relay.contexts.admin.application.unit_of_work import ModerationUnitOfWork
from relay.contexts.admin.domain.errors import MemberNotFoundError
from relay.contexts.admin.domain.members import MemberSummary
from relay.contexts.admin.domain.moderation_log import ModerationLog
from relay.shared.domain import ValueObject

# How much of the trail comes back with the account. Enough to see whether this is the
# first trouble or the fourth; the whole trail is a call of its own.
HISTORY_LENGTH = 20


class MemberDetail(ValueObject):
    """The account, and the last few things moderation did to it."""

    member: MemberSummary
    history: tuple[ModerationLog, ...]


class GetMember:
    """Look one account up.

    The history travels with it on purpose. The question that gets asked at the same
    moment as "who is this" is "have we dealt with them before", and making the person
    asking make a second call to find out is how nobody asks.
    """

    def __init__(self, uow: ModerationUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, *, member_id: int) -> MemberDetail:
        async with self._uow:
            member = await self._uow.members.get(member_id)
            if member is None:
                raise MemberNotFoundError(f"Nobody in Relay answers to {member_id}.")
            history, _ = await self._uow.log.page(
                target_user_id=member_id, limit=HISTORY_LENGTH, offset=0
            )
        return MemberDetail(member=member, history=tuple(history))
