"""The member list: every account, what it has made, and whether it is still switched on."""

from relay.contexts.admin.application.unit_of_work import ModerationUnitOfWork
from relay.contexts.admin.domain.members import MemberSummary


class ListMembers:
    """Read the list somebody runs a Relay from.

    Unlike every other list in Relay this one includes the accounts that have been
    switched off: an admin looking into a complaint needs to find the person it is about
    even when they can no longer post.
    """

    def __init__(self, uow: ModerationUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        *,
        search: str | None,
        is_admin: bool | None,
        deactivated: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MemberSummary], int]:
        """Accounts newest first, and how many there are under those filters."""
        async with self._uow:
            return await self._uow.members.page(
                search=search,
                is_admin=is_admin,
                deactivated=deactivated,
                limit=limit,
                offset=offset,
            )
