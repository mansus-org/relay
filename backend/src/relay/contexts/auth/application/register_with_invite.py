"""Coming in: an invite, a name, a password, and a session that starts in the same breath."""

from dataclasses import dataclass

from relay.contexts.auth.application.issue_tokens import IssueTokens
from relay.contexts.auth.application.unit_of_work import AuthUnitOfWork
from relay.contexts.auth.domain.errors import (
    InviteNotUsableError,
    InviteSpentError,
    UsernameTakenError,
)
from relay.contexts.auth.domain.invite import InviteToken
from relay.contexts.auth.domain.ports import PasswordHasher
from relay.contexts.auth.domain.tokens import TokenPair
from relay.contexts.auth.domain.user import Password, User, Username
from relay.shared.application import Clock


@dataclass(frozen=True)
class Registration:
    """The account a registration made, and the tokens it opens with."""

    user: User
    tokens: TokenPair


class RegisterWithInvite:
    """Spends an invite on a new account. Without a live invite there is no way in."""

    def __init__(
        self,
        uow: AuthUnitOfWork,
        hasher: PasswordHasher,
        issuer: IssueTokens,
        clock: Clock,
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._issuer = issuer
        self._clock = clock

    async def execute(
        self, *, invite_token: str, username: str, password: str, display_name: str
    ) -> Registration:
        async with self._uow:
            invite = await self._uow.invites.get_by_token(InviteToken.parse(invite_token))
            if invite is None:
                raise InviteNotUsableError("No invite matches that token.")
            if not invite.is_open:
                raise InviteSpentError(f"That invite is {invite.state}.")

            if await self._uow.users.get_by_username(Username.parse(username)) is not None:
                raise UsernameTakenError("Someone already has that username.")

            user = User.new(
                username=username,
                display_name=display_name,
                password_hash=self._hasher.hash(str(Password.parse(password))),
            )
            await self._uow.users.add(user)
            invite.redeem(user_id=user.require_id(), at=self._clock.now())
            await self._uow.invites.add(invite)
            tokens = await self._issuer.execute(user.require_id())
            await self._uow.commit()
            return Registration(user=user, tokens=tokens)
