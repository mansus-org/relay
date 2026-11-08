"""Logging in: one answer for every way it can go wrong."""

import pytest

from relay.contexts.auth.application import IssueTokens, Login, RegisterWithInvite
from relay.contexts.auth.domain.errors import InvalidCredentialsError
from relay.contexts.auth.domain.invite import Invite
from relay.contexts.auth.domain.user import Username
from tests.fakes.auth import (
    CountingTokenBroker,
    FakeAuthUnitOfWork,
    PlainPasswordHasher,
)
from tests.fakes.clock import FixedClock


class RecordingHasher(PlainPasswordHasher):
    """Remembers what it was asked to check, so a test can see the work was done."""

    def __init__(self) -> None:
        self.checked: list[str | None] = []

    def verify(self, raw: str, hashed: str | None) -> bool:
        self.checked.append(hashed)
        return super().verify(raw, hashed)


class Wiring:
    """An account made through the front door, and the login that can try it."""

    def __init__(self) -> None:
        self.uow = FakeAuthUnitOfWork()
        self.broker = CountingTokenBroker()
        self.clock = FixedClock()
        issuer = IssueTokens(tokens=self.broker, clock=self.clock, uow=self.uow)
        self.register = RegisterWithInvite(
            uow=self.uow, hasher=PlainPasswordHasher(), issuer=issuer, clock=self.clock
        )
        self.login = Login(uow=self.uow, hasher=PlainPasswordHasher(), issuer=issuer)

    async def an_account(self, username: str = "ada", password: str = "hunter2222") -> None:
        invite = Invite.issue()
        await self.uow.invites.add(invite)
        await self.register.execute(
            invite_token=str(invite.token),
            username=username,
            password=password,
            display_name=username,
        )
        self.broker.issued.clear()  # so a later count is about the login, not this setup


@pytest.fixture
def wiring() -> Wiring:
    return Wiring()


async def test_the_right_password_opens_a_session(wiring: Wiring) -> None:
    await wiring.an_account()

    tokens = await wiring.login.execute(username="ada", password="hunter2222")

    assert tokens.access_token.startswith("access:")
    assert len(str(tokens.refresh_token)) > 30


async def test_the_session_is_recorded_against_the_account(wiring: Wiring) -> None:
    await wiring.an_account()

    tokens = await wiring.login.execute(username="ada", password="hunter2222")

    ada = await wiring.uow.users.get_by_username(Username(value="ada"))
    session = await wiring.uow.refresh_tokens.get_by_token_hash(tokens.refresh_token.fingerprint())
    assert ada is not None
    assert session is not None
    assert session.user_id == ada.require_id()
    assert session.is_active


async def test_a_handle_typed_in_any_case_finds_the_same_account(wiring: Wiring) -> None:
    await wiring.an_account(username="ada")

    await wiring.login.execute(username="ADA", password="hunter2222")

    assert wiring.broker.issued == [1]


async def test_a_login_against_nobody_still_pays_for_a_hash() -> None:
    """A missing account answers as slowly as a wrong password, or the clock tells on us."""
    uow = FakeAuthUnitOfWork()
    hasher = RecordingHasher()
    issuer = IssueTokens(tokens=CountingTokenBroker(), clock=FixedClock(), uow=uow)

    with pytest.raises(InvalidCredentialsError):
        await Login(uow=uow, hasher=hasher, issuer=issuer).execute(
            username="ada", password="hunter2222"
        )

    assert hasher.checked == [None]


async def test_a_password_too_long_for_bcrypt_is_answered_as_wrong(wiring: Wiring) -> None:
    """bcrypt refuses to read this far. The answer is still the one wrong answer there is."""
    await wiring.an_account()
    too_long = "hunter2222" * 20

    with pytest.raises(InvalidCredentialsError):
        await wiring.login.execute(username="ada", password=too_long)
    with pytest.raises(InvalidCredentialsError):
        await wiring.login.execute(username="nobody-here", password=too_long)

    assert wiring.broker.issued == []


async def test_a_wrong_password_gives_the_same_answer_as_a_wrong_name(wiring: Wiring) -> None:
    await wiring.an_account()

    with pytest.raises(InvalidCredentialsError) as wrong_password:
        await wiring.login.execute(username="ada", password="nope-nope-nope")
    with pytest.raises(InvalidCredentialsError) as wrong_name:
        await wiring.login.execute(username="nobody-here", password="hunter2222")

    assert str(wrong_password.value) == str(wrong_name.value)


async def test_a_username_that_could_not_be_typed_is_not_announced_as_one(wiring: Wiring) -> None:
    await wiring.an_account()

    with pytest.raises(InvalidCredentialsError):
        await wiring.login.execute(username="ada lovelace", password="hunter2222")


async def test_a_failed_login_opens_no_session(wiring: Wiring) -> None:
    await wiring.an_account()

    with pytest.raises(InvalidCredentialsError):
        await wiring.login.execute(username="ada", password="wrong-one")

    assert wiring.broker.issued == []


async def test_a_failed_login_writes_nothing_down() -> None:
    clean = Wiring()

    with pytest.raises(InvalidCredentialsError):
        await clean.login.execute(username="ada", password="hunter2222")

    assert clean.uow.committed is False
