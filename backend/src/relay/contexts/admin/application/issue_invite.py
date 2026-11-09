"""Make an invite, and say who it was set aside for."""

from relay.contexts.admin.application.unit_of_work import ModerationUnitOfWork
from relay.contexts.auth.domain.invite import Invite
from relay.contexts.auth.domain.user import User
from relay.shared.application import Clock


class IssueInvite:
    """Hand out a way in.

    Relay is invite-only, so this is the use case that decides who else gets to exist
    here. The note is the part an admin is asked for and the part that is otherwise lost:
    a list of open invites with nothing beside them is a list you cannot remember by
    tomorrow.
    """

    def __init__(self, uow: ModerationUnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, *, admin: User, note: str | None = None) -> Invite:
        invite = Invite.issue(
            created_by_id=admin.require_id(), created_at=self._clock.now(), note=note
        )
        async with self._uow:
            await self._uow.invites.add(invite)
            await self._uow.commit()
            return invite
