"""Reacting to a post: it goes on once, it comes back counted, and it needs a post to sit on."""

from uuid import uuid4

import pytest

from relay.contexts.posts.application import AddReaction
from relay.contexts.posts.domain.post import PostNotFoundError
from relay.contexts.posts.domain.reaction import AlreadyReactedError
from relay.shared.domain import ValidationError
from tests.fakes.clock import FixedClock
from tests.fakes.posts import FakePostsUnitOfWork, a_post


async def test_an_emoji_goes_on_and_comes_back_counted() -> None:
    post = a_post("The bakery on the corner is gone.")
    uow = FakePostsUnitOfWork([post])
    person = uuid4()

    tally = await AddReaction(uow, FixedClock()).execute(
        post_id=post.id, user_id=person, emoji="👍"
    )

    assert uow.committed is True
    assert (tally.emoji, tally.count, tally.user_reacted) == ("👍", 1, True)


async def test_the_same_emoji_twice_from_one_person_is_one_opinion_not_two() -> None:
    post = a_post()
    uow = FakePostsUnitOfWork([post])
    react = AddReaction(uow, FixedClock())
    person = uuid4()
    await react.execute(post_id=post.id, user_id=person, emoji="❤️")

    with pytest.raises(AlreadyReactedError):
        await react.execute(post_id=post.id, user_id=person, emoji="❤️")

    counted = await uow.reactions.tallies([post.id], viewer=person)
    assert [(one.emoji, one.count) for one in counted[post.id]] == [("❤️", 1)]


async def test_a_second_emoji_is_a_different_thing_said() -> None:
    post = a_post()
    uow = FakePostsUnitOfWork([post])
    react = AddReaction(uow, FixedClock())
    person = uuid4()
    await react.execute(post_id=post.id, user_id=person, emoji="❤️")

    tally = await react.execute(post_id=post.id, user_id=person, emoji="🎉")

    assert (tally.emoji, tally.count, tally.user_reacted) == ("🎉", 1, True)
    counted = await uow.reactions.tallies([post.id], viewer=person)
    assert {one.emoji for one in counted[post.id]} == {"❤️", "🎉"}


async def test_two_people_who_feel_the_same_make_it_two() -> None:
    post = a_post()
    uow = FakePostsUnitOfWork([post])
    react = AddReaction(uow, FixedClock())

    mine = await react.execute(post_id=post.id, user_id=uuid4(), emoji="❤️")
    theirs = await react.execute(post_id=post.id, user_id=uuid4(), emoji="❤️")

    assert (mine.count, theirs.count) == (1, 2)
    assert theirs.user_reacted is True


async def test_there_is_nothing_to_react_to() -> None:
    uow = FakePostsUnitOfWork()

    with pytest.raises(PostNotFoundError):
        await AddReaction(uow, FixedClock()).execute(post_id=uuid4(), user_id=uuid4(), emoji="👍")

    assert uow.committed is False


async def test_a_post_taken_down_cannot_be_reacted_to() -> None:
    taken_down = a_post().removed()
    uow = FakePostsUnitOfWork([taken_down])

    with pytest.raises(PostNotFoundError):
        await AddReaction(uow, FixedClock()).execute(
            post_id=taken_down.id, user_id=uuid4(), emoji="👍"
        )

    assert uow.committed is False


async def test_no_emoji_is_no_reaction() -> None:
    post = a_post()
    uow = FakePostsUnitOfWork([post])

    with pytest.raises(ValidationError, match="needs an emoji"):
        await AddReaction(uow, FixedClock()).execute(post_id=post.id, user_id=uuid4(), emoji="   ")

    assert uow.committed is False
