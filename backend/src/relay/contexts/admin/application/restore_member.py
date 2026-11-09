"""Put an account back."""

from relay.contexts.admin.application.unit_of_work import ModerationUnitOfWork
from relay.contexts.admin.domain.errors import (
    AlreadyInThatStateError,
    MemberNotFoundError,
)
from relay.contexts.admin.domain.members import MemberSummary
from relay.contexts.admin.domain.moderation_log import ModerationAction, ModerationLog
from relay.contexts.auth.domain.user import User
from relay.shared.application import Clock


class RestoreMember:
    """Undo a deactivation.

    Nothing is restored but the timestamp: the posts were never touched, so there is
    nothing to bring back, and no session to hand out - they sign in again like anybody
    else. Which is the whole argument for switching people off instead of deleting them.

    Anyone who is an admin can put anyone back, including an account another admin
    switched off. Refusing that would leave a locked-out member waiting on one specific
    person being around.
    """

    def __init__(self, uow: ModerationUnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, *, admin: User, member_id: int, reason: str = "") -> MemberSummary:
        async with self._uow:
            member = await self._uow.members.get(member_id)
            if member is None:
                raise MemberNotFoundError(f"Nobody in Relay answers to {member_id}.")
            if not member.is_deactivated:
                raise AlreadyInThatStateError("That account was never deactivated.")

            at = self._clock.now()
            if not await self._uow.members.set_deactivated(member_id, at=at, on=False):
                raise AlreadyInThatStateError("That account was never deactivated.")
            await self._uow.log.add(
                ModerationLog.for_member(
                    actor_id=admin.require_id(),
                    action=ModerationAction.MEMBER_RESTORED,
                    member=member,
                    reason=reason,
                    created_at=at,
                )
            )
            await self._uow.commit()
            return member.model_copy(update={"deactivated_at": None})
