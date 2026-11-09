"""Handing out tokens: every use case that opens a session goes through here."""

from relay.contexts.auth.application.unit_of_work import AuthUnitOfWork
from relay.contexts.auth.domain.ports import TokenBroker
from relay.contexts.auth.domain.refresh_token import RefreshToken
from relay.contexts.auth.domain.tokens import ACCESS_LIFETIME, RefreshTicket, TokenPair
from relay.shared.application import Clock


class IssueTokens:
    """Signs a short-lived access token and opens a revocable session beside it.

    Not a transaction of its own: it writes into the caller's unit of work, which
    commits the session along with whatever else the request changed.
    """

    def __init__(self, tokens: TokenBroker, clock: Clock, uow: AuthUnitOfWork) -> None:
        self._tokens = tokens
        self._clock = clock
        self._uow = uow

    async def execute(self, user_id: int) -> TokenPair:
        ticket = RefreshTicket.new()
        session = RefreshToken.start(
            user_id=user_id, token_hash=ticket.fingerprint(), now=self._clock.now()
        )
        await self._uow.refresh_tokens.add(session)
        return TokenPair(
            access_token=self._tokens.access_token_for(user_id, lifetime=ACCESS_LIFETIME),
            refresh_token=ticket,
        )
