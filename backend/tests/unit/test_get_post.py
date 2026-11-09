"""Reading one post on its own: there is one, or there is nothing to show."""

import pytest

from relay.contexts.posts.application import GetPost
from relay.contexts.posts.domain.post import PostNotFoundError
from tests.fakes.posts import FakePostsUnitOfWork, a_post


async def test_a_post_is_there_to_read() -> None:
    post = a_post("The bakery on the corner is gone.")
    assert await GetPost(FakePostsUnitOfWork([post])).execute(post.id) == post


async def test_a_post_that_was_never_said_is_not_there() -> None:
    with pytest.raises(PostNotFoundError):
        await GetPost(FakePostsUnitOfWork()).execute(a_post().id)


async def test_a_removed_post_is_not_there_either() -> None:
    post = a_post().removed()
    with pytest.raises(PostNotFoundError):
        await GetPost(FakePostsUnitOfWork([post])).execute(post.id)
