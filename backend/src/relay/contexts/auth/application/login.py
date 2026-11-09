"""Going back in: prove who you are, get a session."""

from relay.contexts.auth.application.issue_tokens import IssueTokens
from relay.contexts.auth.application.unit_of_work import AuthUnitOfWork
from relay.contexts.auth.domain.errors import (
    AccountDeactivatedError,
    InvalidCredentialsError,
    InvalidUsernameError,
)
from relay.contexts.auth.domain.ports import PasswordHasher
from relay.contexts.auth.domain.tokens import TokenPair
from relay.contexts.auth.domain.user import MAX_PASSWORD_BYTES, Username


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
            if len(password.encode()) > MAX_PASSWORD_BYTES:
                # bcrypt reads this little and would rather raise than try. Long is wrong,
                # said the same way as any other wrong, and before anyone is looked up.
                raise InvalidCredentialsError("Username or password is wrong.")
            user = await self._uow.users.get_by_username(handle)
            # A missing account and a wrong password have to look identical from outside,
            # in what they say and in how long they take. So the hash is asked either way:
            # with nobody found it is asked against a hash of nothing, and a stopwatch
            # cannot tell the two answers apart.
            matches = self._hasher.verify(password, None if user is None else user.password_hash)
            if user is None or not matches:
                raise InvalidCredentialsError("Username or password is wrong.")
            if user.is_deactivated:
                # Said only once the password has been proved, so it tells a stranger
                # nothing and tells the person on the other side what they need to know:
                # their password is fine, and somebody in charge has switched them off.
                raise AccountDeactivatedError(
                    "That account has been deactivated. Ask whoever runs your Relay."
                )

            tokens = await self._issuer.execute(user.require_id())
            await self._uow.commit()
            return tokens
