"""Taking a reaction back: it comes off, and there is nothing to take back that was never left."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from relay.contexts.posts.application import RemoveReaction
from relay.contexts.posts.domain.reaction import Reaction, ReactionNotFoundError
from tests.fakes.posts import FakePostsUnitOfWork, a_post


async def with_reactions(post_id: UUID, *who_and_emoji: tuple[UUID, str]) -> FakePostsUnitOfWork:
    """A unit of work holding one reaction per pair given: who left it, and what they left."""
    uow = FakePostsUnitOfWork()
    for person, emoji in who_and_emoji:
        await uow.reactions.add(
            Reaction.given(
                post_id=post_id,
                user_id=person,
                emoji=emoji,
                created_at=datetime(2026, 3, 4, 9, 30, tzinfo=UTC),
            )
        )
    return uow


async def test_an_emoji_comes_back_off() -> None:
    post = a_post()
    person = uuid4()
    uow = await with_reactions(post.id, (person, "❤️"))

    await RemoveReaction(uow).execute(post_id=post.id, user_id=person, emoji="❤️")

    assert uow.committed is True
    assert (await uow.reactions.tallies([post.id]))[post.id] == ()


async def test_taking_back_what_you_never_left_is_reported() -> None:
    post = a_post()
    uow = await with_reactions(post.id, (uuid4(), "❤️"))

    with pytest.raises(ReactionNotFoundError):
        await RemoveReaction(uow).execute(post_id=post.id, user_id=uuid4(), emoji="❤️")

    assert uow.committed is False


async def test_someone_elses_emoji_is_not_yours_to_take() -> None:
    post = a_post()
    theirs = uuid4()
    uow = await with_reactions(post.id, (theirs, "❤️"))

    with pytest.raises(ReactionNotFoundError):
        await RemoveReaction(uow).execute(post_id=post.id, user_id=uuid4(), emoji="❤️")

    counted = await uow.reactions.tallies([post.id], viewer=theirs)
    assert [(one.emoji, one.count, one.user_reacted) for one in counted[post.id]] == [
        ("❤️", 1, True)
    ]


async def test_only_the_emoji_asked_for_comes_off() -> None:
    post = a_post()
    person = uuid4()
    uow = await with_reactions(post.id, (person, "❤️"), (person, "🎉"))

    await RemoveReaction(uow).execute(post_id=post.id, user_id=person, emoji="❤️")

    counted = await uow.reactions.tallies([post.id], viewer=person)
    assert [(one.emoji, one.count) for one in counted[post.id]] == [("🎉", 1)]
