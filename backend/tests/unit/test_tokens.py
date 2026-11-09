"""Refresh tickets: what a client holds between calls, and why the database cannot read it."""

import pytest

from relay.contexts.auth.domain.errors import InvalidTokenError
from relay.contexts.auth.domain.tokens import ACCESS_LIFETIME, RefreshTicket, TokenPair


def test_a_ticket_is_a_long_random_string_and_shows_up_in_a_link() -> None:
    ticket = RefreshTicket.new()

    assert len(str(ticket)) > 30
    assert str(ticket) == ticket.value


def test_two_tickets_never_match() -> None:
    assert str(RefreshTicket.new()) != str(RefreshTicket.new())


def test_a_ticket_is_read_back_from_the_string_a_client_sent() -> None:
    assert str(RefreshTicket.parse("  abc123  ")) == "abc123"


def test_no_ticket_at_all_is_not_a_ticket() -> None:
    with pytest.raises(InvalidTokenError):
        RefreshTicket.parse("   ")


def test_the_database_holds_a_fingerprint_and_never_the_ticket() -> None:
    ticket = RefreshTicket.new()

    fingerprint = ticket.fingerprint()

    assert len(fingerprint) == 64
    assert fingerprint != str(ticket)
    assert RefreshTicket(value=ticket.value).fingerprint() == fingerprint


def test_a_pair_is_both_halves_and_the_access_token_is_good_for_fifteen_minutes() -> None:
    pair = TokenPair(access_token="jwt", refresh_token=RefreshTicket.new())

    assert pair.access_token == "jwt"
    assert ACCESS_LIFETIME.total_seconds() == 900
