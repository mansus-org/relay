"""An invite: one link, one person, and the ways it stops being usable."""

from datetime import UTC, datetime, timedelta

import pytest

from relay.contexts.auth.domain.errors import InviteNotUsableError, InviteSpentError
from relay.contexts.auth.domain.invite import Invite, InviteToken

LATER = datetime(2026, 1, 2, tzinfo=UTC)


def test_a_fresh_invite_is_open_and_carries_no_person_yet() -> None:
    invite = Invite.issue()
    assert invite.is_open
    assert invite.used_by_id is None
    assert invite.created_by_id is None


def test_two_invites_never_share_a_token() -> None:
    assert str(Invite.issue().token) != str(Invite.issue().token)


def test_an_invite_link_is_the_token_and_nothing_else() -> None:
    assert str(InviteToken.parse("  dGhpcyBpcyBub3QgYSB1dWlk  ")) == "dGhpcyBpcyBub3QgYSB1dWlk"


@pytest.mark.parametrize("raw", ["", "   "])
def test_an_empty_invite_token_is_not_usable(raw: str) -> None:
    with pytest.raises(InviteNotUsableError):
        InviteToken.parse(raw)


def test_redeeming_an_invite_binds_it_to_the_account_and_closes_it() -> None:
    invite = Invite.issue()

    invite.redeem(user_id=7, at=LATER)

    assert invite.used_by_id == 7
    assert invite.used_at == LATER
    assert not invite.is_open


def test_an_invite_only_opens_once() -> None:
    invite = Invite.issue()
    invite.redeem(user_id=7, at=LATER)

    with pytest.raises(InviteSpentError):
        invite.redeem(user_id=8, at=LATER.replace(day=3))


def test_an_invite_pulled_before_it_was_used_never_opens() -> None:
    invite = Invite.issue()

    invite.revoke(at=LATER)

    assert not invite.is_open
    assert invite.revoked_at == LATER
    with pytest.raises(InviteSpentError):
        invite.redeem(user_id=7, at=LATER + timedelta(days=1))
