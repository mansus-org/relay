"""What makes a post a post: it has to be said, it has to fit, and it can be taken down."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from relay.contexts.posts.domain.post import MAX_BODY_LENGTH, ModerationStatus, Post
from relay.shared.domain import ValidationError
from tests.fakes.posts import a_post


def test_a_post_keeps_what_was_said_and_when() -> None:
    author = uuid4()
    when = datetime(2026, 3, 4, 9, 30, tzinfo=UTC)
    post = Post.write(author_id=author, body="The bakery on the corner is gone.", created_at=when)
    assert post.author_id == author
    assert post.body == "The bakery on the corner is gone."
    assert post.created_at == when
    assert post.moderation_status is ModerationStatus.PENDING


def test_the_spaces_around_a_post_are_not_part_of_it() -> None:
    post = Post.write(author_id=uuid4(), body="  hello  ", created_at=datetime.now(UTC))
    assert post.body == "hello"


@pytest.mark.parametrize("body", ["", "   ", "\n\t"])
def test_nothing_said_is_no_post(body: str) -> None:
    with pytest.raises(ValidationError, match="needs some text"):
        Post.write(author_id=uuid4(), body=body, created_at=datetime.now(UTC))


def test_a_post_fits_exactly_in_what_the_compose_screen_allows() -> None:
    longest = "a" * MAX_BODY_LENGTH
    assert Post.write(author_id=uuid4(), body=longest, created_at=datetime.now(UTC)).body == longest


def test_one_character_over_is_refused_with_the_limit_in_the_message() -> None:
    with pytest.raises(ValidationError, match=str(MAX_BODY_LENGTH)):
        Post.write(
            author_id=uuid4(), body="a" * (MAX_BODY_LENGTH + 1), created_at=datetime.now(UTC)
        )


def test_a_post_said_without_a_locality_reaches_no_locality_feed() -> None:
    assert not a_post(cell=None).shows_in_locality_feed


def test_a_post_said_in_a_locality_reaches_that_locality() -> None:
    assert a_post(cell="883920cd1bfffff").shows_in_locality_feed


@pytest.mark.parametrize("status", [ModerationStatus.PENDING, ModerationStatus.APPROVED])
def test_a_post_still_up_reaches_the_feed(status: ModerationStatus) -> None:
    post = a_post().model_copy(update={"moderation_status": status})
    assert post.shows_in_locality_feed


def test_a_removed_post_reaches_no_feed_but_is_still_there() -> None:
    post = a_post().removed()
    assert post.moderation_status is ModerationStatus.REMOVED
    assert not post.shows_in_locality_feed


def test_a_reply_is_only_a_post_that_answers_another() -> None:
    root = uuid4()
    reply = Post.write(
        author_id=uuid4(),
        body="Back Monday.",
        created_at=datetime.now(UTC),
        parent_id=root,
    )
    assert reply.parent_id == root


def test_a_post_that_answers_nothing_is_not_a_reply() -> None:
    assert a_post().parent_id is None


def test_a_reply_is_said_where_the_post_it_answers_was() -> None:
    """A reply does not have to say where it is: it belongs where its parent does."""
    community = uuid4()
    root = a_post(cell="there", community_id=community)

    reply = Post.reply_to(
        root, author_id=uuid4(), body="Back Monday.", created_at=datetime.now(UTC)
    )

    assert reply.parent_id == root.id
    assert reply.location_cell == "there"
    assert reply.community_id == community


def test_a_reply_said_somewhere_else_is_still_the_same_thread() -> None:
    """Someone answering from a different street still answers the same post."""
    root = a_post(cell="there")

    reply = Post.reply_to(
        root,
        author_id=uuid4(),
        body="I am in Vigo reading this.",
        created_at=datetime.now(UTC),
        location_cell="here",
    )

    assert reply.location_cell == "here"


def test_a_reply_cannot_move_the_thread_to_another_community() -> None:
    """An answer in another community is a different conversation, not a reply."""
    root = a_post(community_id=uuid4())

    with pytest.raises(ValidationError, match="community its parent is in"):
        Post.reply_to(
            root,
            author_id=uuid4(),
            body="Over here instead.",
            created_at=datetime.now(UTC),
            community_id=uuid4(),
        )


def test_a_reply_cannot_join_a_community_its_parent_never_joined() -> None:
    root = a_post(community_id=None)

    with pytest.raises(ValidationError, match="community its parent is in"):
        Post.reply_to(
            root,
            author_id=uuid4(),
            body="Is this a community post now?",
            created_at=datetime.now(UTC),
            community_id=uuid4(),
        )
