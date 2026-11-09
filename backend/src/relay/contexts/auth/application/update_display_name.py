"""Changing what Relay calls you."""

from relay.contexts.auth.application.unit_of_work import AuthUnitOfWork
from relay.contexts.auth.domain.user import DisplayName, User
from relay.shared.domain import NotFoundError


class UpdateDisplayName:
    """Writes a new display name over the one an account already has.

    The handle someone logs in with is not up for grabs: it is how other people's
    posts and invites refer to them, and changing it would quietly rewrite history.
    """

    def __init__(self, uow: AuthUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, *, user_id: int, display_name: str) -> User:
        async with self._uow:
            user = await self._uow.users.get(user_id)
            if user is None:
                raise NotFoundError("That account is gone.")
            # The value decides what counts as a name; the endpoint does not get to skip it.
            user.display_name = DisplayName.parse(display_name)
            # `add` merges by id, so this is the write-back and not a second account.
            await self._uow.users.add(user)
            await self._uow.commit()
            return user
