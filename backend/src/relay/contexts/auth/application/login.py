"""Going back in: prove who you are, get a session."""

from relay.contexts.auth.application.issue_tokens import IssueTokens
from relay.contexts.auth.application.unit_of_work import AuthUnitOfWork
from relay.contexts.auth.domain.errors import InvalidCredentialsError, InvalidUsernameError
from relay.contexts.auth.domain.ports import PasswordHasher
from relay.contexts.auth.domain.tokens import TokenPair
from relay.contexts.auth.domain.user import Username


class Login:
    """Checks a password and opens a session for whoever it belonged to."""

    def __init__(self, uow: AuthUnitOfWork, hasher: PasswordHasher, issuer: IssueTokens) -> None:
        self._uow = uow
        self._hasher = hasher
        self._issuer = issuer

    async def execute(self, *, username: str, password: str) -> TokenPair:
        async with self._uow:
            try:
                handle = Username.parse(username)
            except InvalidUsernameError:
                # A handle that is not a handle still only means: we cannot find you. Anything
                # sharper would turn the login form into a list of who has a Relay account.
                raise InvalidCredentialsError("Username or password is wrong.") from None
            user = await self._uow.users.get_by_username(handle)
            # A missing account and a wrong password have to look identical from outside,
            # or the login form becomes a list of everyone with a Relay account.
            if user is None or not self._hasher.verify(password, user.password_hash):
                raise InvalidCredentialsError("Username or password is wrong.")

            tokens = await self._issuer.execute(user.require_id())
            await self._uow.commit()
            return tokens
