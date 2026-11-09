"""The invites somebody running a Relay has handed out, or could not get rid of."""

from relay.contexts.admin.application.unit_of_work import ModerationUnitOfWork
from relay.contexts.auth.domain.invite import Invite


class ListInvites:
    """Read the invite list.

    Filterable by state because the two questions people ask are different ones: "how
    many of these are still live" when deciding whether to make more, and "who is this
    one for" when somebody arrives claiming you sent it.
    """

    def __init__(self, uow: ModerationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self, *, state: str | None, limit: int, offset: int
    ) -> tuple[list[Invite], int]:
        async with self._uow:
            return await self._uow.invites.page(state=state, limit=limit, offset=offset)
