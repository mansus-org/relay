"""Renaming yourself: the domain owns the rules, and the write is one transaction."""

import pytest

from relay.contexts.auth.application import UpdateDisplayName
from relay.contexts.auth.domain.errors import InvalidDisplayNameError
from relay.contexts.auth.domain.user import MAX_DISPLAY_NAME_CHARS, User
from relay.shared.domain import NotFoundError
from tests.fakes.auth import FakeAuthUnitOfWork


def renaming(uow: FakeAuthUnitOfWork) -> UpdateDisplayName:
    return UpdateDisplayName(uow=uow)


async def an_account(uow: FakeAuthUnitOfWork) -> User:
    user = User.new(
        username="ada_lovelace",
        display_name="Ada Lovelace",
        password_hash="hashed:hunter2222",
    )
    await uow.users.add(user)
    return user


async def test_a_new_name_replaces_the_old_one() -> None:
    uow = FakeAuthUnitOfWork()
    user = await an_account(uow)

    updated = await renaming(uow).execute(user_id=user.require_id(), display_name="Ada L.")

    assert str(updated.display_name) == "Ada L."
    stored = await uow.users.get(user.require_id())
    assert stored is not None and str(stored.display_name) == "Ada L."
    assert uow.committed


async def test_the_handle_you_log_in_with_is_not_up_for_grabs() -> None:
    uow = FakeAuthUnitOfWork()
    user = await an_account(uow)

    updated = await renaming(uow).execute(
        user_id=user.require_id(), display_name="Countess of Lovelace"
    )

    assert str(updated.username) == "ada_lovelace"
    assert await uow.users.count() == 1


async def test_a_name_keeps_what_it_was_never_meant_to_have() -> None:
    """Nobody meant a space at either end of their own name."""
    uow = FakeAuthUnitOfWork()
    user = await an_account(uow)

    updated = await renaming(uow).execute(user_id=user.require_id(), display_name="  Ada L.  ")

    assert str(updated.display_name) == "Ada L."


async def test_a_name_that_breaks_a_rule_is_refused_before_anything_is_written() -> None:
    uow = FakeAuthUnitOfWork()
    user = await an_account(uow)

    with pytest.raises(InvalidDisplayNameError):
        await renaming(uow).execute(user_id=user.require_id(), display_name="   ")

    stored = await uow.users.get(user.require_id())
    assert stored is not None and str(stored.display_name) == "Ada Lovelace"
    assert not uow.committed


async def test_a_name_too_long_to_fit_on_a_line_is_refused() -> None:
    uow = FakeAuthUnitOfWork()
    user = await an_account(uow)

    with pytest.raises(InvalidDisplayNameError):
        await renaming(uow).execute(
            user_id=user.require_id(), display_name="x" * (MAX_DISPLAY_NAME_CHARS + 1)
        )

    assert not uow.committed


async def test_an_account_that_is_gone_has_nothing_to_rename() -> None:
    uow = FakeAuthUnitOfWork()

    with pytest.raises(NotFoundError):
        await renaming(uow).execute(user_id=99, display_name="Nobody")

    assert not uow.committed
