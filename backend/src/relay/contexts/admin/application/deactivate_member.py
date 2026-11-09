"""Switch an account off, and cut the sessions it was holding open."""

from relay.contexts.admin.application.unit_of_work import ModerationUnitOfWork
from relay.contexts.admin.domain.errors import (
    AlreadyInThatStateError,
    MemberNotFoundError,
)
from relay.contexts.admin.domain.members import MemberSummary, can_deactivate
from relay.contexts.admin.domain.moderation_log import ModerationAction, ModerationLog
from relay.contexts.auth.domain.user import User
from relay.shared.application import Clock
from relay.shared.domain import ValueObject


class Deactivation(ValueObject):
    """An account as it is now that it is off, and how many sessions went with it."""

    member: MemberSummary
    sessions_ended: int


class DeactivateMember:
    """Take somebody out of Relay without deleting anything they made.

    The account is not removed. Their handle stays theirs, their posts stay where they
    are, and all that changes is one timestamp - so this can be undone, and so throwing
    out a member cannot quietly rewrite the history of a conversation they were in.

    What does go is every session they had open, in the same transaction as the switch:
    an account that is off but still signed in is not off, it only looks that way until
    the next request.
    """

    def __init__(self, uow: ModerationUnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, *, admin: User, member_id: int, reason: str) -> Deactivation:
        async with self._uow:
            member = await self._uow.members.get(member_id)
            if member is None:
                raise MemberNotFoundError(f"Nobody in Relay answers to {member_id}.")
            can_deactivate(admin=admin, target=member)
            if member.is_deactivated:
                raise AlreadyInThatStateError("That account is already deactivated.")

            at = self._clock.now()
            if not await self._uow.members.set_deactivated(member_id, at=at, on=True):
                # Read as open a moment ago and closed by the time this write landed:
                # two admins, one click each, one of them gets told the state.
                raise AlreadyInThatStateError("That account is already deactivated.")
            ended = await self._uow.members.end_sessions(member_id, at=at)
            await self._uow.log.add(
                ModerationLog.for_member(
                    actor_id=admin.require_id(),
                    action=ModerationAction.MEMBER_DEACTIVATED,
                    member=member,
                    reason=reason,
                    created_at=at,
                )
            )
            await self._uow.commit()
            return Deactivation(
                member=member.model_copy(update={"deactivated_at": at}), sessions_ended=ended
            )
