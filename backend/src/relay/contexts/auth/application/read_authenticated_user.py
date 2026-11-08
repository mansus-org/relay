"""Who a bearer token belongs to. Every protected route starts here."""

from relay.contexts.auth.application.unit_of_work import AuthUnitOfWork
from relay.contexts.auth.domain.errors import InvalidTokenError
from relay.contexts.auth.domain.ports import TokenBroker
from relay.contexts.auth.domain.user import User


class ReadAuthenticatedUser:
    """Turns an access token into the account behind it."""

    def __init__(self, uow: AuthUnitOfWork, tokens: TokenBroker) -> None:
        self._uow = uow
        self._tokens = tokens

    async def execute(self, access_token: str) -> User:
        user_id = self._tokens.user_id_of(access_token)
        async with self._uow:
            user = await self._uow.users.get(user_id)
        if user is None:
            # Signed and in date, and still no account: it went away after the token was minted.
            raise InvalidTokenError("That token belongs to an account that is gone.")
        return user
