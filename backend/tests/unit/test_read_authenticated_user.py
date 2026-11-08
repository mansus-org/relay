"""Reading the account behind an access token."""

import pytest

from relay.contexts.auth.application import ReadAuthenticatedUser
from relay.contexts.auth.domain.errors import InvalidTokenError
from relay.contexts.auth.domain.user import User
from tests.fakes.auth import CountingTokenBroker, FakeAuthUnitOfWork


def read_from(uow: FakeAuthUnitOfWork) -> ReadAuthenticatedUser:
    return ReadAuthenticatedUser(uow=uow, tokens=CountingTokenBroker())


async def an_account() -> FakeAuthUnitOfWork:
    uow = FakeAuthUnitOfWork()
    await uow.users.add(
        User.new(username="ada", display_name="Ada", password_hash="hashed:hunter2222")
    )
    return uow


async def test_a_token_we_signed_gives_back_its_account() -> None:
    uow = await an_account()

    user = await read_from(uow).execute("access:1:1800")

    assert str(user.username) == "ada"


async def test_a_token_for_an_account_that_is_gone_is_not_a_token() -> None:
    with pytest.raises(InvalidTokenError):
        await read_from(FakeAuthUnitOfWork()).execute("access:1:1800")


async def test_a_string_that_is_not_one_of_our_tokens_is_refused() -> None:
    uow = await an_account()

    with pytest.raises(InvalidTokenError):
        await read_from(uow).execute("hunter2")


async def test_reading_a_token_does_not_change_anything() -> None:
    uow = await an_account()

    await read_from(uow).execute("access:1:1800")

    assert uow.committed is False
