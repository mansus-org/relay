"""Refreshing: a session traded in, and the ways a ticket is refused."""

from datetime import timedelta

import pytest

from relay.contexts.auth.application import IssueTokens, RefreshAccessToken
from relay.contexts.auth.domain.errors import InvalidTokenError
from relay.contexts.auth.domain.refresh_token import REFRESH_LIFETIME
from relay.contexts.auth.domain.tokens import RefreshTicket
from relay.contexts.auth.domain.user import User
from tests.fakes.auth import CountingTokenBroker, FakeAuthUnitOfWork
from tests.fakes.clock import FixedClock


class Wiring:
    """One account with one live session, and the refresh that can spend it."""

    def __init__(
        self, *, clock: FixedClock | None = None, somebody_else_wins: bool = False
    ) -> None:
        self.uow = FakeAuthUnitOfWork(somebody_else_won=somebody_else_wins)
        self.clock = clock or FixedClock()
        self.broker = CountingTokenBroker()
        self.issuer = IssueTokens(tokens=self.broker, clock=self.clock, uow=self.uow)
        self.refresh = RefreshAccessToken(uow=self.uow, issuer=self.issuer, clock=self.clock)

    async def a_session(self) -> RefreshTicket:
        await self.uow.users.add(
            User.new(username="ada", display_name="Ada", password_hash="hashed:hunter2222")
        )
        pair = await self.issuer.execute(1)
        return pair.refresh_token


async def test_a_live_ticket_buys_a_new_pair() -> None:
    wiring = Wiring()
    ticket = await wiring.a_session()

    renewed = await wiring.refresh.execute(str(ticket))

    assert renewed.access_token.startswith("access:")
    assert str(renewed.refresh_token) != str(ticket)


async def test_the_ticket_that_was_just_used_stops_working() -> None:
    wiring = Wiring()
    ticket = await wiring.a_session()
    await wiring.refresh.execute(str(ticket))

    with pytest.raises(InvalidTokenError):
        await wiring.refresh.execute(str(ticket))


async def test_using_a_ticket_leaves_exactly_one_live_session() -> None:
    wiring = Wiring()
    ticket = await wiring.a_session()

    renewed = await wiring.refresh.execute(str(ticket))

    spent = await wiring.uow.refresh_tokens.get_by_token_hash(ticket.fingerprint())
    fresh = await wiring.uow.refresh_tokens.get_by_token_hash(renewed.refresh_token.fingerprint())
    assert spent is not None and not spent.is_active
    assert fresh is not None and fresh.is_active


async def test_the_one_who_arrives_second_with_the_same_ticket_gets_nothing() -> None:
    """Two requests, one session. The loser is refused on the write and mints no tokens."""
    wiring = Wiring(somebody_else_wins=True)
    ticket = await wiring.a_session()

    with pytest.raises(InvalidTokenError):
        await wiring.refresh.execute(str(ticket))

    assert not wiring.uow.committed
    assert wiring.uow.rolled_back
    assert len(wiring.broker.issued) == 1  # the one this test started with, and no second


async def test_a_ticket_never_issued_is_refused() -> None:
    wiring = Wiring()
    await wiring.a_session()

    with pytest.raises(InvalidTokenError):
        await wiring.refresh.execute(str(RefreshTicket.new()))


async def test_a_ticket_past_its_thirtieth_day_is_refused() -> None:
    wiring = Wiring()
    ticket = await wiring.a_session()
    much_later = FixedClock(FixedClock().now() + REFRESH_LIFETIME + timedelta(minutes=1))

    late = RefreshAccessToken(
        uow=wiring.uow,
        issuer=IssueTokens(tokens=wiring.broker, clock=much_later, uow=wiring.uow),
        clock=much_later,
    )

    with pytest.raises(InvalidTokenError):
        await late.execute(str(ticket))


async def test_a_session_revoked_by_hand_is_refused() -> None:
    wiring = Wiring()
    ticket = await wiring.a_session()
    session = await wiring.uow.refresh_tokens.get_by_token_hash(ticket.fingerprint())
    assert session is not None
    session.revoke(at=FixedClock().now())
    await wiring.uow.refresh_tokens.add(session)

    with pytest.raises(InvalidTokenError):
        await wiring.refresh.execute(str(ticket))


async def test_a_refresh_does_not_make_a_second_account() -> None:
    wiring = Wiring()
    ticket = await wiring.a_session()

    await wiring.refresh.execute(str(ticket))

    assert await wiring.uow.users.count() == 1
    assert wiring.broker.issued[-1] == 1
