"""Registering with an invite: the only door into Relay."""

import pytest

from relay.contexts.auth.application import IssueTokens, RegisterWithInvite
from relay.contexts.auth.domain.errors import (
    InvalidPasswordError,
    InviteNotUsableError,
    InviteSpentError,
    UsernameTakenError,
)
from relay.contexts.auth.domain.invite import Invite
from tests.fakes.auth import (
    CountingTokenBroker,
    FakeAuthUnitOfWork,
    PlainPasswordHasher,
)
from tests.fakes.clock import FixedClock


class Wiring:
    """The service on fakes, with the broker and the data it can see in reach."""

    def __init__(self) -> None:
        self.uow = FakeAuthUnitOfWork()
        self.broker = CountingTokenBroker()
        self.clock = FixedClock()
        self.register = RegisterWithInvite(
            uow=self.uow,
            hasher=PlainPasswordHasher(),
            issuer=IssueTokens(tokens=self.broker, clock=self.clock, uow=self.uow),
            clock=self.clock,
        )

    async def invite(self) -> Invite:
        invite = Invite.issue()
        await self.uow.invites.add(invite)
        return invite

    async def as_(self, username: str, password: str, invite: Invite):
        return await self.register.execute(
            invite_token=str(invite.token),
            username=username,
            password=password,
            display_name=username.title(),
        )


async def test_an_invite_opens_exactly_one_account_and_hands_over_two_tokens() -> None:
    wiring = Wiring()
    invite = await wiring.invite()

    registration = await wiring.as_("ada", "hunter2222", invite)

    assert str(registration.user.username) == "ada"
    assert registration.user.id is not None
    assert registration.tokens.access_token.startswith("access:")
    assert wiring.broker.issued == [registration.user.require_id()]
    assert wiring.uow.committed


async def test_what_gets_stored_is_the_hash_and_not_the_password() -> None:
    wiring = Wiring()
    invite = await wiring.invite()

    registration = await wiring.as_("ada", "hunter2222", invite)

    assert registration.user.password_hash == "hashed:hunter2222"


async def test_each_invite_ends_up_spent_by_the_account_it_opened() -> None:
    wiring = Wiring()
    spare, adas, graces = await wiring.invite(), await wiring.invite(), await wiring.invite()
    await wiring.as_("someone", "hunter0000", spare)

    ada = await wiring.as_("ada", "hunter2222", adas)
    grace = await wiring.as_("grace", "hunter3333", graces)

    for invite, username in ((adas, "ada"), (graces, "grace")):
        spent = await wiring.uow.invites.get_by_token(invite.token)
        assert spent is not None
        assert spent.used_at == FixedClock().now()
        assert spent.used_by_id is not None
        who = await wiring.uow.users.get(spent.used_by_id)
        assert who is not None and str(who.username) == username
    assert ada.user.require_id() != grace.user.require_id()


async def test_a_spent_invite_does_not_open_a_second_account() -> None:
    wiring = Wiring()
    invite = await wiring.invite()
    await wiring.as_("ada", "hunter2222", invite)

    with pytest.raises(InviteSpentError):
        await wiring.as_("grace", "hunter3333", invite)


async def test_a_token_that_is_not_an_invite_is_not_usable() -> None:
    wiring = Wiring()

    with pytest.raises(InviteNotUsableError):
        await wiring.register.execute(
            invite_token="cheese", username="ada", password="hunter2222", display_name="Ada"
        )
    assert not wiring.uow.committed


async def test_a_revoked_invite_does_not_open_anything() -> None:
    wiring = Wiring()
    invite = Invite.issue()
    invite.revoke(at=FixedClock().now())
    await wiring.uow.invites.add(invite)

    with pytest.raises(InviteSpentError):
        await wiring.as_("ada", "hunter2222", invite)


async def test_a_handle_somebody_already_has_is_refused() -> None:
    wiring = Wiring()
    first, second = await wiring.invite(), await wiring.invite()
    await wiring.as_("ada", "hunter2222", first)

    with pytest.raises(UsernameTakenError):
        await wiring.as_("ada", "hunter3333", second)


async def test_a_password_too_short_to_keep_an_account_is_refused() -> None:
    wiring = Wiring()
    invite = await wiring.invite()

    with pytest.raises(InvalidPasswordError):
        await wiring.as_("ada", "short", invite)
    assert await wiring.uow.users.count() == 0


async def test_the_display_name_they_chose_is_the_one_kept() -> None:
    wiring = Wiring()
    invite = await wiring.invite()

    registration = await wiring.register.execute(
        invite_token=str(invite.token), username="ada", password="hunter2222", display_name="Ada L."
    )

    assert registration.user.name == "Ada L."
