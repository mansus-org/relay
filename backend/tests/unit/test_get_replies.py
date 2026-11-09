"""The replies under one post: the ones said to it, in the order they were said."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from relay.contexts.posts.application import GetReplies
from relay.contexts.posts.domain.post import Post, PostNotFoundError
from tests.fakes.posts import FakePostsUnitOfWork, a_post

START = datetime(2026, 3, 4, 9, 0, tzinfo=UTC)


def said_in_reply_to(post_id: UUID, text: str, minutes: int) -> Post:
    return a_post(text, parent_id=post_id, at=START + timedelta(minutes=minutes))


async def test_the_replies_come_back_in_the_order_they_were_said() -> None:
    root = a_post("Is the bakery closing for good?")
    first = said_in_reply_to(root.id, "Mine closed in January.", 5)
    second = said_in_reply_to(root.id, "They are on holiday, back Monday.", 12)
    uow = FakePostsUnitOfWork([root, second, first])

    replies = await GetReplies(uow).execute(root.id)

    assert [post.body for post in replies] == [
        "Mine closed in January.",
        "They are on holiday, back Monday.",
    ]


async def test_a_reply_to_a_reply_is_under_its_own_reply() -> None:
    """One level per call: the client opens a thread a step at a time if it wants to."""
    root = a_post("Is the bakery closing for good?")
    answer = said_in_reply_to(root.id, "They are on holiday, back Monday.", 5)
    answer_to_the_answer = a_post("Thanks!", parent_id=answer.id, at=START + timedelta(minutes=9))
    uow = FakePostsUnitOfWork([root, answer, answer_to_the_answer])

    assert [post.body for post in await GetReplies(uow).execute(root.id)] == [
        "They are on holiday, back Monday."
    ]
    assert [post.body for post in await GetReplies(uow).execute(answer.id)] == ["Thanks!"]


async def test_a_post_that_was_never_said_has_no_thread() -> None:
    uow = FakePostsUnitOfWork()

    with pytest.raises(PostNotFoundError):
        await GetReplies(uow).execute(a_post().id)


async def test_a_taken_down_post_shows_no_thread() -> None:
    taken_down = a_post("Rude, apparently.").removed()
    uow = FakePostsUnitOfWork([taken_down, said_in_reply_to(taken_down.id, "Indeed.", 1)])

    with pytest.raises(PostNotFoundError):
        await GetReplies(uow).execute(taken_down.id)


async def test_a_taken_down_reply_is_not_in_the_thread() -> None:
    root = a_post("Is the bakery closing for good?")
    uow = FakePostsUnitOfWork(
        [
            root,
            said_in_reply_to(root.id, "Keep it clean.", 1).removed(),
            said_in_reply_to(root.id, "Back Monday.", 2),
        ]
    )

    assert [post.body for post in await GetReplies(uow).execute(root.id)] == ["Back Monday."]
