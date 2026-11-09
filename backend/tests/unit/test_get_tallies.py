"""What sits under a list of posts: the emoji people left and how many replies, counted once."""

from datetime import UTC, datetime
from uuid import uuid4

from relay.contexts.posts.application import GetTallies
from relay.contexts.posts.domain.reaction import Reaction
from tests.fakes.posts import FakePostsUnitOfWork, a_post

NOW = datetime(2026, 3, 4, 9, 30, tzinfo=UTC)


async def test_a_post_answers_what_people_left_on_it() -> None:
    root = a_post("Is the bakery closing for good?")
    answer = a_post("Back Monday.", parent_id=root.id)
    uow = FakePostsUnitOfWork([root, answer, a_post("Thanks!", parent_id=root.id)])
    for _ in range(2):
        await uow.reactions.add(
            Reaction.given(post_id=root.id, user_id=uuid4(), emoji="❤️", created_at=NOW)
        )

    tallies = await GetTallies(uow).execute([root.id, answer.id])

    assert [(one.emoji, one.count) for one in tallies[root.id].reactions] == [("❤️", 2)]
    assert tallies[root.id].reply_count == 2
    # A reply of its own is answered too, and answers nothing.
    assert tallies[answer.id].reply_count == 0
    assert tallies[answer.id].reactions == ()


async def test_the_reader_sees_their_own_emoji_marked() -> None:
    root = a_post("Is the bakery closing for good?")
    mine = uuid4()
    uow = FakePostsUnitOfWork([root])
    await uow.reactions.add(
        Reaction.given(post_id=root.id, user_id=mine, emoji="👍", created_at=NOW)
    )
    await uow.reactions.add(
        Reaction.given(post_id=root.id, user_id=uuid4(), emoji="👍", created_at=NOW)
    )

    tallies = await GetTallies(uow).execute([root.id], viewer=mine)

    assert [(one.emoji, one.count, one.user_reacted) for one in tallies[root.id].reactions] == [
        ("👍", 2, True)
    ]

    public = await GetTallies(uow).execute([root.id])
    assert [one.user_reacted for one in public[root.id].reactions] == [False]


async def test_a_post_nobody_answered_is_still_answered() -> None:
    root = a_post("Is the bakery closing for good?")

    tallies = await GetTallies(FakePostsUnitOfWork([root])).execute([root.id])

    assert tallies[root.id].reply_count == 0
    assert tallies[root.id].reactions == ()


async def test_nothing_asked_is_nothing_answered() -> None:
    assert await GetTallies(FakePostsUnitOfWork()).execute([]) == {}
