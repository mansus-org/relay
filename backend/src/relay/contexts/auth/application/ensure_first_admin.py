"""An empty Relay has to be able to get its first account."""

from relay.contexts.auth.application.unit_of_work import AuthUnitOfWork
from relay.contexts.auth.domain.ports import PasswordHasher
from relay.contexts.auth.domain.user import Password, User


class EnsureFirstAdmin:
    """Create the first account, and never a second one.

    Invite-only is a hard rule, so on a fresh database the only way in would be
    hand-writing a row. This is the door that lets an operator set the first
    account from configuration; once anybody exists it does nothing at all.
    """

    def __init__(self, uow: AuthUnitOfWork, hasher: PasswordHasher) -> None:
        self._uow = uow
        self._hasher = hasher

    async def execute(self, *, username: str, password: str) -> User | None:
        """The account that was created, or None if there was no need for one."""
        async with self._uow:
            if await self._uow.users.count() > 0:
                return None
            user = User.new(
                username=username,
                display_name=username,
                password_hash=self._hasher.hash(str(Password.parse(password))),
                is_admin=True,
            )
            await self._uow.users.add(user)
            await self._uow.commit()
            return user
