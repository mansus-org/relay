"""The first account: the one that gets in without an invite, and only ever once."""

import pytest

from relay.contexts.auth.application import EnsureFirstAdmin
from relay.contexts.auth.domain.errors import InvalidPasswordError
from relay.contexts.auth.domain.user import User
from tests.fakes.auth import FakeAuthUnitOfWork, PlainPasswordHasher


def seeder(uow: FakeAuthUnitOfWork) -> EnsureFirstAdmin:
    return EnsureFirstAdmin(uow=uow, hasher=PlainPasswordHasher())


async def test_an_empty_relay_creates_the_admin_it_was_asked_for() -> None:
    uow = FakeAuthUnitOfWork()

    created = await seeder(uow).execute(username="root", password="hunter2222")

    assert created is not None
    assert created.is_admin
    assert uow.committed


async def test_the_admin_is_hashed_before_it_is_stored() -> None:
    uow = FakeAuthUnitOfWork()

    created = await seeder(uow).execute(username="root", password="hunter2222")

    assert created is not None
    stored = await uow.users.get_by_username(created.username)
    assert stored is not None
    assert stored.password_hash == "hashed:hunter2222"


async def test_the_second_startup_does_not_make_a_second_anyone() -> None:
    uow = FakeAuthUnitOfWork()
    await uow.users.add(
        User.new(username="someone", display_name="Someone", password_hash="hashed:hunter2222")
    )

    created = await seeder(uow).execute(username="root", password="hunter2222")

    assert created is None
    assert await uow.users.count() == 1


async def test_a_password_too_short_to_belong_to_an_admin_is_refused() -> None:
    uow = FakeAuthUnitOfWork()

    with pytest.raises(InvalidPasswordError):
        await seeder(uow).execute(username="root", password="nope")
    assert await uow.users.count() == 0


async def test_the_first_admin_is_called_by_their_own_handle() -> None:
    uow = FakeAuthUnitOfWork()

    created = await seeder(uow).execute(username="root", password="hunter2222")

    assert created is not None and created.name == "root"
