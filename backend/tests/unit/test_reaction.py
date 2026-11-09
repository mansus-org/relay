"""An emoji left on a post: one person, one emoji, and nothing that is not an emoji."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from relay.contexts.posts.domain.reaction import MAX_EMOJI_LENGTH, Reaction, ReactionTally
from relay.shared.domain import ValidationError


def left_on(emoji: str) -> Reaction:
    return Reaction.given(
        post_id=uuid4(), user_id=uuid4(), emoji=emoji, created_at=datetime.now(UTC)
    )


def test_a_reaction_keeps_who_left_it_where_and_when() -> None:
    post, person = uuid4(), uuid4()
    when = datetime(2026, 3, 4, 9, 30, tzinfo=UTC)

    reaction = Reaction.given(post_id=post, user_id=person, emoji="👍", created_at=when)

    assert (reaction.post_id, reaction.user_id, reaction.emoji, reaction.created_at) == (
        post,
        person,
        "👍",
        when,
    )


@pytest.mark.parametrize("emoji", ["", "   ", "\n\t"])
def test_no_emoji_is_no_reaction(emoji: str) -> None:
    with pytest.raises(ValidationError, match="needs an emoji"):
        left_on(emoji)


def test_a_phrase_is_not_an_emoji() -> None:
    with pytest.raises(ValidationError, match="one emoji"):
        left_on("i love it")


def test_the_spaces_around_an_emoji_are_not_part_of_it() -> None:
    assert left_on("  👍  ").emoji == "👍"


def test_one_character_over_is_refused_with_the_limit_in_the_message() -> None:
    with pytest.raises(ValidationError, match=str(MAX_EMOJI_LENGTH)):
        left_on("a" * (MAX_EMOJI_LENGTH + 1))


def test_a_whole_family_fits_under_the_limit() -> None:
    """Four people and the joiners between them are still one emoji, and one opinion."""
    family = "👨‍👩‍👧‍👦"
    assert len(family) < MAX_EMOJI_LENGTH
    assert left_on(family).emoji == family


def test_an_emoji_nobody_else_has_left_still_counts_as_one() -> None:
    tally = ReactionTally(emoji="👍", count=1)
    assert tally.user_reacted is False
