"""Staying signed in: trade the long-lived token for a short one, before the short one dies."""

from dataclasses import dataclass

from relay.contexts.auth.application.issue_tokens import IssueTokens
from relay.contexts.auth.application.unit_of_work import AuthUnitOfWork
from relay.contexts.auth.domain.errors import InvalidTokenError
from relay.contexts.auth.domain.tokens import RefreshTicket
from relay.shared.application import Clock


@dataclass(frozen=True)
class RenewedSession:
    """A fresh access token, and the refresh token that replaces the one just spent."""

    access_token: str
    refresh_token: RefreshTicket


class RefreshAccessToken:
    """Rotates the session: the ticket that was just used is dead from here on."""

    def __init__(self, uow: AuthUnitOfWork, issuer: IssueTokens, clock: Clock) -> None:
        self._uow = uow
        self._issuer = issuer
        self._clock = clock

    async def execute(self, raw_ticket: str) -> RenewedSession:
        async with self._uow:
            ticket = RefreshTicket.parse(raw_ticket)
            session = await self._uow.refresh_tokens.get_by_token_hash(ticket.fingerprint())
            now = self._clock.now()
            if session is None or not session.is_active or session.is_expired(now):
                raise InvalidTokenError("That refresh token is no good any more.")

            session.revoke(at=now)
            await self._uow.refresh_tokens.add(session)
            fresh = await self._issuer.execute(session.user_id)
            await self._uow.commit()
            return RenewedSession(
                access_token=fresh.access_token, refresh_token=fresh.refresh_token
            )
