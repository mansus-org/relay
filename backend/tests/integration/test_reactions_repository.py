"""The reactions table: one emoji per person per post, and the counts a feed needs."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.contexts.posts.domain.post import Post
from relay.contexts.posts.domain.reaction import Reaction
from relay.contexts.posts.infrastructure.unit_of_work import SqlAlchemyPostsUnitOfWork
from relay.shared.infrastructure.database import create_session_factory

START = datetime(2026, 3, 4, 12, tzinfo=UTC)


@pytest.fixture
async def uow(migrated_engine: AsyncEngine) -> AsyncIterator[SqlAlchemyPostsUnitOfWork]:
    unit = SqlAlchemyPostsUnitOfWork(create_session_factory(migrated_engine))
    async with unit:
        yield unit


def left_on(post_id: UUID, user_id: UUID, emoji: str, *, minutes: int = 0) -> Reaction:
    return Reaction.given(
        post_id=post_id,
        user_id=user_id,
        emoji=emoji,
        created_at=START + timedelta(minutes=minutes),
    )


async def a_post(uow: SqlAlchemyPostsUnitOfWork) -> UUID:
    """A post to leave something on: a reaction's key says it must be one that exists."""
    post = Post.write(author_id=uuid4(), body="Is the bakery closing for good?", created_at=START)
    await uow.posts.add(post)
    await uow.commit()
    return post.id


async def test_a_reaction_comes_back_as_it_was_left(uow: SqlAlchemyPostsUnitOfWork) -> None:
    post, person = await a_post(uow), uuid4()
    reaction = left_on(post, person, "👍")

    await uow.reactions.add(reaction)
    await uow.commit()

    back = await uow.reactions.get(post_id=post, user_id=person, emoji="👍")
    assert back is not None
    assert (back.post_id, back.user_id, back.emoji) == (post, person, "👍")


async def test_who_has_not_reacted_has_left_nothing(uow: SqlAlchemyPostsUnitOfWork) -> None:
    assert await uow.reactions.get(post_id=uuid4(), user_id=uuid4(), emoji="👍") is None


async def test_the_same_emoji_twice_from_one_person_cannot_be_stored(
    uow: SqlAlchemyPostsUnitOfWork,
) -> None:
    """The database holds the rule, so two writers at once cannot both win."""
    post, person = await a_post(uow), uuid4()

    await uow.reactions.add(left_on(post, person, "❤️"))
    await uow.commit()
    with pytest.raises(IntegrityError):
        await uow.reactions.add(left_on(post, person, "❤️", minutes=1))
        await uow.commit()


async def test_a_different_emoji_from_the_same_person_is_a_different_row(
    uow: SqlAlchemyPostsUnitOfWork,
) -> None:
    post, person = await a_post(uow), uuid4()

    await uow.reactions.add(left_on(post, person, "❤️"))
    await uow.reactions.add(left_on(post, person, "🎉"))
    await uow.commit()

    assert [one.emoji for one in (await uow.reactions.tallies([post]))[post]] == ["❤️", "🎉"]


async def test_taking_a_reaction_back_leaves_nothing(uow: SqlAlchemyPostsUnitOfWork) -> None:
    post, person = await a_post(uow), uuid4()
    await uow.reactions.add(left_on(post, person, "❤️"))
    await uow.commit()

    assert await uow.reactions.remove(post_id=post, user_id=person, emoji="❤️") is True
    await uow.commit()

    assert await uow.reactions.get(post_id=post, user_id=person, emoji="❤️") is None


async def test_taking_back_what_was_never_left_says_so(uow: SqlAlchemyPostsUnitOfWork) -> None:
    post, person = await a_post(uow), uuid4()
    await uow.reactions.add(left_on(post, person, "❤️"))
    await uow.commit()

    assert await uow.reactions.remove(post_id=post, user_id=uuid4(), emoji="❤️") is False
    assert await uow.reactions.remove(post_id=post, user_id=person, emoji="🎉") is False


async def test_the_counts_come_back_with_the_most_used_emoji_first(
    uow: SqlAlchemyPostsUnitOfWork,
) -> None:
    posts = [await a_post(uow), await a_post(uow)]
    for person in (uuid4(), uuid4(), uuid4()):
        await uow.reactions.add(left_on(posts[0], person, "❤️"))
    await uow.reactions.add(left_on(posts[0], uuid4(), "🎉"))
    await uow.commit()

    counted = await uow.reactions.tallies(posts)

    assert [(one.emoji, one.count) for one in counted[posts[0]]] == [("❤️", 3), ("🎉", 1)]
    assert counted[posts[1]] == ()


async def test_the_reader_sees_their_own_emoji_marked(uow: SqlAlchemyPostsUnitOfWork) -> None:
    post, mine = await a_post(uow), uuid4()
    await uow.reactions.add(left_on(post, mine, "👍"))
    await uow.reactions.add(left_on(post, uuid4(), "👍"))
    await uow.commit()

    counted = await uow.reactions.tallies([post], viewer=mine)

    assert [(one.emoji, one.count, one.user_reacted) for one in counted[post]] == [("👍", 2, True)]

    public = await uow.reactions.tallies([post])
    assert [one.user_reacted for one in public[post]] == [False]
