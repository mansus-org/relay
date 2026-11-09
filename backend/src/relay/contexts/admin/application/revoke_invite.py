"""Pull an invite back before anybody uses it."""

from relay.contexts.admin.application.unit_of_work import ModerationUnitOfWork
from relay.contexts.admin.domain.errors import (
    AlreadyInThatStateError,
    InviteNotFoundError,
)
from relay.contexts.auth.domain.invite import Invite
from relay.shared.application import Clock


class RevokeInvite:
    """Close an invite that is still going.

    Only an open one. An invite that has been spent already did its one job, and stamping
    it revoked afterwards would change nothing about the account it let in while making
    the list look like it had been stopped. So the answer to that one is simply: it is
    used.
    """

    def __init__(self, uow: ModerationUnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, *, invite_id: int) -> Invite:
        async with self._uow:
            invite = await self._uow.invites.get(invite_id)
            if invite is None:
                raise InviteNotFoundError(f"There is no invite {invite_id} to pull back.")
            if not invite.is_open:
                raise AlreadyInThatStateError(f"That invite is already {invite.state}.")

            at = self._clock.now()
            if not await self._uow.invites.revoke(invite, at=at):
                # Open when it was read, closed by the time this landed.
                raise AlreadyInThatStateError("That invite is no longer open.")
            invite.revoke(at=at)
            await self._uow.commit()
            return invite
