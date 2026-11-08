"""The writes that have to survive two people at once, against a real migrated database.

The fakes let a use case pretend it read a row and then wrote it back. These three are
the parts of auth where that would be a lie: the database has to decide the winner, and
the loser has to be told.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.contexts.auth.domain.errors import UsernameTakenError
from relay.contexts.auth.domain.invite import Invite
from relay.contexts.auth.domain.refresh_token import RefreshToken
from relay.contexts.auth.domain.user import User
from relay.contexts.auth.infrastructure.unit_of_work import SqlAlchemyAuthUnitOfWork
from relay.shared.infrastructure.database import create_session_factory

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
async def uow(migrated_engine: AsyncEngine) -> AsyncIterator[SqlAlchemyAuthUnitOfWork]:
    unit = SqlAlchemyAuthUnitOfWork(create_session_factory(migrated_engine))
    async with unit:
        yield unit


async def test_an_invite_is_spent_by_the_first_write_and_by_nobody_after_it(
    uow: SqlAlchemyAuthUnitOfWork,
) -> None:
    ada = User.new(username="ada", display_name="Ada", password_hash="x")
    grace = User.new(username="grace", display_name="Grace", password_hash="y")
    await uow.users.add(ada)
    await uow.users.add(grace)
    invite = Invite.issue()
    await uow.invites.add(invite)

    first = await uow.invites.redeem(invite, user_id=ada.require_id(), at=NOW)
    second = await uow.invites.redeem(invite, user_id=grace.require_id(), at=NOW)

    assert (first, second) == (True, False)


async def test_a_session_is_ended_by_the_first_write_and_by_nobody_after_it(
    uow: SqlAlchemyAuthUnitOfWork,
) -> None:
    ada = User.new(username="ada", display_name="Ada", password_hash="x")
    await uow.users.add(ada)
    session = RefreshToken.start(user_id=ada.require_id(), token_hash="a-fingerprint", now=NOW)
    await uow.refresh_tokens.add(session)

    first = await uow.refresh_tokens.revoke(session, at=NOW)
    second = await uow.refresh_tokens.revoke(session, at=NOW)

    assert (first, second) == (True, False)


async def test_the_database_is_what_refuses_a_second_account_on_one_handle(
    uow: SqlAlchemyAuthUnitOfWork,
) -> None:
    await uow.users.add(User.new(username="ada", display_name="Ada", password_hash="x"))
    await uow.commit()

    with pytest.raises(UsernameTakenError):
        await uow.users.add(User.new(username="Ada", display_name="Ada L.", password_hash="y"))
