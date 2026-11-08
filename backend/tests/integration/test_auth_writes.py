"""The writes two people can race into, against a real migrated database.

The fakes let a use case read a row and write it back as if nobody else had touched it.
These are the parts of auth where that would be a lie: the database decides the winner,
and the loser has to be told in a way the use case can act on.

Every test here keeps two units of work open at once and lets one of them write from a
row it read before the other one wrote. A repository that only looked at the copy in its
own memory - which is what the fake does - would pass without these and fail with them.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.contexts.auth.domain.errors import InviteSpentError, UsernameTakenError
from relay.contexts.auth.domain.invite import Invite
from relay.contexts.auth.domain.refresh_token import RefreshToken
from relay.contexts.auth.domain.user import User
from relay.contexts.auth.infrastructure.unit_of_work import SqlAlchemyAuthUnitOfWork
from relay.shared.infrastructure.database import create_session_factory

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def a_unit_of_work(engine: AsyncEngine) -> SqlAlchemyAuthUnitOfWork:
    """A transaction of someone else's, the way two requests each have one."""
    return SqlAlchemyAuthUnitOfWork(create_session_factory(engine))


async def test_the_first_writer_spends_the_invite_and_the_second_is_refused(
    migrated_engine: AsyncEngine,
) -> None:
    ada = User.new(username="ada", display_name="Ada", password_hash="x")
    grace = User.new(username="grace", display_name="Grace", password_hash="y")
    invite = Invite.issue()
    async with a_unit_of_work(migrated_engine) as seed:
        await seed.users.add(ada)
        await seed.users.add(grace)
        await seed.invites.add(invite)
        await seed.commit()

    async with (
        a_unit_of_work(migrated_engine) as first,
        a_unit_of_work(migrated_engine) as second,
    ):
        # Both look before either writes, which is the only way these two can overlap.
        mine = await first.invites.get_by_token(invite.token)
        theirs = await second.invites.get_by_token(invite.token)
        assert mine is not None and theirs is not None

        assert await first.invites.redeem(mine, user_id=ada.require_id(), at=NOW) is True
        await first.commit()

        # The second is still holding the copy it read, and that copy still says: open.
        assert theirs.is_open
        assert await second.invites.redeem(theirs, user_id=grace.require_id(), at=NOW) is False


async def test_the_first_writer_ends_the_session_and_the_second_is_refused(
    migrated_engine: AsyncEngine,
) -> None:
    ada = User.new(username="ada", display_name="Ada", password_hash="x")
    async with a_unit_of_work(migrated_engine) as seed:
        await seed.users.add(ada)
        await seed.refresh_tokens.add(
            RefreshToken.start(user_id=ada.require_id(), token_hash="a-fingerprint", now=NOW)
        )
        await seed.commit()

    async with (
        a_unit_of_work(migrated_engine) as first,
        a_unit_of_work(migrated_engine) as second,
    ):
        mine = await first.refresh_tokens.get_by_token_hash("a-fingerprint")
        theirs = await second.refresh_tokens.get_by_token_hash("a-fingerprint")
        assert mine is not None and theirs is not None

        assert await first.refresh_tokens.revoke(mine, at=NOW) is True
        await first.commit()

        assert theirs.is_active
        assert await second.refresh_tokens.revoke(theirs, at=NOW) is False


async def test_the_loser_of_an_invite_race_leaves_no_account_behind(
    migrated_engine: AsyncEngine,
) -> None:
    """What the losing use case leans on: everything it wrote before it lost is unwound."""
    grace = User.new(username="grace", display_name="Grace", password_hash="x")
    invite = Invite.issue()
    async with a_unit_of_work(migrated_engine) as seed:
        await seed.users.add(grace)
        await seed.invites.add(invite)
        await seed.commit()

    async with (
        a_unit_of_work(migrated_engine) as winner,
        a_unit_of_work(migrated_engine) as loser,
    ):
        mine = await winner.invites.get_by_token(invite.token)
        theirs = await loser.invites.get_by_token(invite.token)
        assert mine is not None and theirs is not None
        assert await winner.invites.redeem(mine, user_id=grace.require_id(), at=NOW) is True
        await winner.commit()

        with pytest.raises(InviteSpentError):
            # The same three steps RegisterWithInvite takes when it loses: the account is
            # already written here, the invite comes back refused, the transaction unwinds.
            await loser.users.add(User.new(username="ada", display_name="Ada", password_hash="y"))
            if not await loser.invites.redeem(theirs, user_id=grace.require_id(), at=NOW):
                raise InviteSpentError("Someone else spent that invite.")

    async with a_unit_of_work(migrated_engine) as after:
        assert await after.users.count() == 1


async def test_the_database_is_what_refuses_a_second_account_on_one_handle(
    migrated_engine: AsyncEngine,
) -> None:
    async with a_unit_of_work(migrated_engine) as unit:
        await unit.users.add(User.new(username="ada", display_name="Ada", password_hash="x"))
        await unit.commit()

        # "Ada" is folded to "ada" on the way in, so this only collides because the index
        # says so - which is the one thing that can promise it across two writers.
        with pytest.raises(UsernameTakenError):
            await unit.users.add(User.new(username="Ada", display_name="Ada L.", password_hash="y"))


async def test_the_table_itself_refuses_a_handle_with_a_capital_in_it(
    migrated_engine: AsyncEngine,
) -> None:
    """Lowercase is the domain's rule; the CHECK is what makes it hold for anything else."""
    async with a_unit_of_work(migrated_engine) as unit:
        with pytest.raises(IntegrityError):
            await unit.session.execute(
                text(
                    "insert into users (username, display_name, password_hash, is_admin)"
                    " values ('Ada', 'Ada', 'x', false)"
                )
            )
