"""A session row: the fingerprint of a ticket, and the day it stops counting."""

from datetime import UTC, datetime, timedelta

from relay.contexts.auth.domain.refresh_token import REFRESH_LIFETIME, RefreshToken
from relay.contexts.auth.domain.tokens import RefreshTicket

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def a_session() -> RefreshToken:
    return RefreshToken.start(user_id=7, token_hash=RefreshTicket.new().fingerprint(), now=NOW)


def test_a_session_expires_thirty_days_after_it_was_opened() -> None:
    session = a_session()

    assert session.user_id == 7
    assert session.created_at == NOW
    assert session.expires_at == NOW + REFRESH_LIFETIME
    assert session.is_active


def test_a_session_is_still_active_the_minute_before_it_expires() -> None:
    session = a_session()

    assert not session.is_expired(NOW + REFRESH_LIFETIME - timedelta(seconds=1))
    assert session.is_expired(NOW + REFRESH_LIFETIME)


def test_a_revoked_session_is_not_active_whatever_the_clock_says() -> None:
    session = a_session()

    session.revoke(at=NOW)

    assert not session.is_active
    assert session.revoked_at == NOW


def test_the_stored_value_is_a_fingerprint_not_the_ticket() -> None:
    ticket = RefreshTicket.new()

    session = RefreshToken.start(user_id=1, token_hash=ticket.fingerprint(), now=NOW)

    assert session.token_hash == ticket.fingerprint()
    assert str(ticket) not in str(session)


def test_a_session_from_a_row_carries_its_own_expiry() -> None:
    late = datetime(2026, 3, 1, tzinfo=UTC)

    assert RefreshToken(user_id=1, token_hash="x" * 64, expires_at=late, created_at=NOW).is_expired(
        datetime(2026, 4, 1, tzinfo=UTC)
    )
