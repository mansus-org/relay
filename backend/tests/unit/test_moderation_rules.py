"""The rules behind the admin endpoints.

What may be decided about a post, what has to be said when you decide it, and who may be
switched off. Each one is written down here so it can be read without running the API.
"""

from datetime import UTC, datetime

import pytest

from relay.contexts.admin.domain.errors import (
    AlreadyInThatStateError,
    MemberCannotBeDeactivatedError,
)
from relay.contexts.admin.domain.members import MemberSummary, can_deactivate
from relay.contexts.admin.domain.moderation_log import (
    MAX_REASON_LENGTH,
    ModerationAction,
    ModerationLog,
)
from relay.contexts.admin.domain.review import ReviewAction, rule_for
from relay.contexts.auth.domain.user import User
from relay.contexts.posts.domain.post import ModerationStatus
from relay.shared.domain import ValidationError
from tests.fakes.posts import a_post

NOW = datetime(2026, 3, 4, 9, 30, tzinfo=UTC)


def an_admin(id: int) -> User:
    """An admin account with a row number, which is the only way to tell two of them apart."""
    return User.new("root_admin", "Root", "a-hash", is_admin=True).model_copy(update={"id": id})


def an_account(id: int, *, admin: bool = False) -> MemberSummary:
    return MemberSummary(
        id=id,
        username="ada_lovelace",
        display_name="Ada Lovelace",
        is_admin=admin,
        created_at=NOW,
    )


# --- what may be decided about a post --------------------------------------------------


def test_each_action_names_where_it_leaves_a_post_and_where_it_applies_from() -> None:
    """The table at the bottom of review.py, written out where somebody can read it."""
    assert rule_for(ReviewAction.APPROVE).leaves is ModerationStatus.APPROVED
    assert rule_for(ReviewAction.APPROVE).only_from == frozenset({ModerationStatus.PENDING})

    assert rule_for(ReviewAction.REMOVE).leaves is ModerationStatus.REMOVED
    # A post that has been read can still be taken down: nobody looks at everything
    # before it goes out.
    assert rule_for(ReviewAction.REMOVE).only_from == frozenset(
        {ModerationStatus.PENDING, ModerationStatus.APPROVED}
    )

    # A restored post is an approved one, not a third thing.
    assert rule_for(ReviewAction.RESTORE).leaves is ModerationStatus.APPROVED
    assert rule_for(ReviewAction.RESTORE).only_from == frozenset({ModerationStatus.REMOVED})


def test_each_action_is_written_down_as_itself() -> None:
    assert rule_for(ReviewAction.APPROVE).logged_as is ModerationAction.APPROVED
    assert rule_for(ReviewAction.REMOVE).logged_as is ModerationAction.REMOVED
    assert rule_for(ReviewAction.RESTORE).logged_as is ModerationAction.RESTORED


def test_approving_a_post_that_is_waiting_marks_it_and_leaves_it_readable() -> None:
    decided = rule_for(ReviewAction.APPROVE).apply(a_post())
    assert decided.moderation_status is ModerationStatus.APPROVED
    assert decided.is_up


def test_removing_takes_a_post_down_and_restoring_puts_it_back() -> None:
    down = rule_for(ReviewAction.REMOVE).apply(a_post())
    assert down.moderation_status is ModerationStatus.REMOVED
    assert not down.is_up

    back = rule_for(ReviewAction.RESTORE).apply(down)
    assert back.moderation_status is ModerationStatus.APPROVED
    assert back.is_up


def test_a_second_approval_says_what_the_post_already_is() -> None:
    decided = rule_for(ReviewAction.APPROVE).apply(a_post())
    with pytest.raises(AlreadyInThatStateError, match="already approved"):
        rule_for(ReviewAction.APPROVE).apply(decided)


def test_removing_a_post_that_is_already_down_says_so() -> None:
    down = rule_for(ReviewAction.REMOVE).apply(a_post())
    with pytest.raises(AlreadyInThatStateError, match="already removed"):
        rule_for(ReviewAction.REMOVE).apply(down)


@pytest.mark.parametrize(
    ("action", "where_it_is"),
    [
        (ReviewAction.RESTORE, ModerationStatus.PENDING),
        (ReviewAction.APPROVE, ModerationStatus.REMOVED),
    ],
)
def test_a_move_that_skips_over_the_queue_is_refused(
    action: ReviewAction, where_it_is: ModerationStatus
) -> None:
    post = a_post().model_copy(update={"moderation_status": where_it_is})
    with pytest.raises(AlreadyInThatStateError, match=f"cannot be {action.value}"):
        rule_for(action).apply(post)


# --- what has to be said about it ------------------------------------------------------


def test_a_line_about_a_post_keeps_who_decided_and_what_about() -> None:
    post = a_post()
    entry = ModerationLog.for_post(
        actor_id=7,
        action=ModerationAction.REMOVED,
        post=post,
        reason="Selling medicine",
        created_at=NOW,
    )
    assert entry.actor_id == 7
    assert entry.action is ModerationAction.REMOVED
    assert entry.post_id == post.id
    assert entry.community_id == post.community_id
    assert entry.reason == "Selling medicine"
    assert entry.target_user_id is None
    assert entry.created_at == NOW


def test_a_line_about_an_account_keeps_the_account_and_no_post() -> None:
    entry = ModerationLog.for_member(
        actor_id=7,
        action=ModerationAction.MEMBER_DEACTIVATED,
        member=an_account(12),
        reason="Harassment",
        created_at=NOW,
    )
    assert entry.action is ModerationAction.MEMBER_DEACTIVATED
    assert entry.target_user_id == 12
    assert entry.post_id is None
    assert entry.reason == "Harassment"


def test_taking_a_post_down_without_saying_why_is_refused() -> None:
    with pytest.raises(ValidationError, match="needs a reason"):
        ModerationLog.for_post(
            actor_id=1, action=ModerationAction.REMOVED, post=a_post(), reason="   ", created_at=NOW
        )


def test_switching_an_account_off_without_saying_why_is_refused() -> None:
    with pytest.raises(ValidationError, match="needs a reason"):
        ModerationLog.for_member(
            actor_id=1,
            action=ModerationAction.MEMBER_DEACTIVATED,
            member=an_account(12),
            reason="",
            created_at=NOW,
        )


def test_putting_a_thing_back_does_not_have_to_say_why() -> None:
    """The absence of a problem is hard to file, so nobody is made to invent one."""
    approved = ModerationLog.for_post(
        actor_id=1, action=ModerationAction.APPROVED, post=a_post(), reason="", created_at=NOW
    )
    restored = ModerationLog.for_post(
        actor_id=1, action=ModerationAction.RESTORED, post=a_post(), reason="   ", created_at=NOW
    )
    back_on = ModerationLog.for_member(
        actor_id=1,
        action=ModerationAction.MEMBER_RESTORED,
        member=an_account(12),
        reason="",
        created_at=NOW,
    )
    assert (approved.reason, restored.reason, back_on.reason) == ("", "", "")


def test_a_reason_is_trimmed_to_what_it_actually_said() -> None:
    entry = ModerationLog.for_post(
        actor_id=1,
        action=ModerationAction.REMOVED,
        post=a_post(),
        reason="  Advertising  ",
        created_at=NOW,
    )
    assert entry.reason == "Advertising"


def test_a_reason_fits_exactly_and_one_character_over_does_not() -> None:
    fits = ModerationLog.for_post(
        actor_id=1,
        action=ModerationAction.REMOVED,
        post=a_post(),
        reason="x" * MAX_REASON_LENGTH,
        created_at=NOW,
    )
    assert len(fits.reason) == MAX_REASON_LENGTH

    with pytest.raises(ValidationError, match=str(MAX_REASON_LENGTH)):
        ModerationLog.for_post(
            actor_id=1,
            action=ModerationAction.REMOVED,
            post=a_post(),
            reason="x" * (MAX_REASON_LENGTH + 1),
            created_at=NOW,
        )


# --- who may be switched off -----------------------------------------------------------


def test_a_member_may_be_switched_off() -> None:
    assert can_deactivate(admin=an_admin(1), target=an_account(2)) is None


def test_nobody_switches_themselves_off() -> None:
    """The only tool that switches you back on is the one you are holding."""
    with pytest.raises(MemberCannotBeDeactivatedError, match="your own account"):
        can_deactivate(admin=an_admin(1), target=an_account(1))


def test_an_admin_cannot_be_switched_off_over_this_api() -> None:
    with pytest.raises(MemberCannotBeDeactivatedError, match="Make them a member first"):
        can_deactivate(admin=an_admin(1), target=an_account(2, admin=True))


def test_an_account_that_is_on_is_not_off_and_one_that_is_off_is() -> None:
    """What the two routes read to answer 409 when asked for what is already the case."""
    assert not an_account(2).is_deactivated
    assert an_account(2, admin=True).is_admin
    assert an_account(3).model_copy(update={"deactivated_at": NOW}).is_deactivated
