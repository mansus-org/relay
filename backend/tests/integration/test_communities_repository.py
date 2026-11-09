"""The communities and community_members tables: what goes in comes back out, and the
counting, the anchoring and the feed filter are the SQL's, so they are tested in SQL.

The API tests cover the same ground through HTTP; they cannot reach the two unique keys
(FastAPI turns a duplicate name into a fresh slug before it gets here) or the counted
subqueries with nobody in them.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.contexts.communities.domain.community import Community
from relay.contexts.communities.domain.membership import Membership
from relay.contexts.communities.infrastructure.unit_of_work import (
    SqlAlchemyCommunitiesUnitOfWork,
)
from relay.contexts.posts.domain.post import ModerationStatus, Post
from relay.contexts.posts.infrastructure.models import PostModel
from relay.shared.domain import ConflictError
from relay.shared.infrastructure.database import create_session_factory

START = datetime(2026, 3, 4, 12, tzinfo=UTC)
VIGO = "883920cd1bfffff"
TOKYO = timezone(timedelta(hours=9))


@pytest.fixture
async def uow(migrated_engine: AsyncEngine) -> AsyncIterator[SqlAlchemyCommunitiesUnitOfWork]:
    unit = SqlAlchemyCommunitiesUnitOfWork(create_session_factory(migrated_engine))
    async with unit:
        yield unit


def founded(*, name: str = "Vigo Book Club", minutes: int = 0, **fields: Any) -> Community:
    return Community.start(
        name=name, created_by=uuid4(), created_at=START + timedelta(minutes=minutes), **fields
    )


async def founded_as(uow: SqlAlchemyCommunitiesUnitOfWork, *communities: Community) -> None:
    for community in communities:
        await uow.communities.add(community)
    await uow.commit()


async def joined_as(
    uow: SqlAlchemyCommunitiesUnitOfWork,
    community: Community,
    *,
    who: UUID,
    pseudonym: str | None = None,
) -> Membership:
    membership = Membership.join(community, user_id=who, joined_at=START, pseudonym=pseudonym)
    await uow.members.add(membership)
    await uow.commit()
    return membership


def said(*, community: UUID | None, minutes: int = 0, taken_down: bool = False) -> Post:
    post = Post.write(
        author_id=uuid4(),
        body="The bakery on the corner is gone.",
        created_at=START + timedelta(minutes=minutes),
        community_id=community,
    )
    return post.removed() if taken_down else post


async def said_as(uow: SqlAlchemyCommunitiesUnitOfWork, *posts: Post) -> None:
    """Posts go in through the posts table, which this context only ever reads."""
    for post in posts:
        uow.session.add(PostModel.from_domain(post))
    await uow.commit()


# A community.


async def test_a_community_comes_back_as_it_was_saved(uow) -> None:
    community = founded(
        name="O Camiño",
        description="Walkers, Wednesdays.",
        location_cell=VIGO,
        radius_km=12,
        allow_pseudonyms=True,
    )
    await founded_as(uow, community)

    got = await uow.communities.get(community.id)

    assert got is not None
    assert got.id == community.id
    assert got.name == "O Camiño"
    assert got.slug == "o-camino"
    assert got.description == "Walkers, Wednesdays."
    assert got.location_cell == VIGO
    assert got.radius_km == 12
    assert got.allow_pseudonyms is True
    assert got.created_by == community.created_by
    assert got.created_at == community.created_at


async def test_a_community_that_was_never_founded_is_not_there(uow) -> None:
    assert await uow.communities.get(uuid4()) is None


async def test_a_community_about_a_subject_keeps_its_empty_place(uow) -> None:
    community = founded(name="Long Distance Walkers")
    await founded_as(uow, community)

    got = await uow.communities.get(community.id)

    assert (got.location_cell, got.radius_km) == (None, None)


# Who is looking.


async def test_a_community_is_counted_for_whoever_is_looking(uow) -> None:
    """`member_count` and `is_member` are not columns: they are read out of the members
    table for the person asking, and a community read without a viewer is nobody's
    member."""
    community = founded()
    await founded_as(uow, community)
    stranger, member = uuid4(), uuid4()

    alone = await uow.communities.get_for(community.id, viewer=None)
    assert (alone.member_count, alone.is_member) == (0, False)
    assert (await uow.communities.get_for(community.id, viewer=stranger)).is_member is False

    await joined_as(uow, community, who=member)

    counted = await uow.communities.get_for(community.id, viewer=member)
    assert (counted.member_count, counted.is_member) == (1, True)
    assert (await uow.communities.get_for(community.id, viewer=stranger)).is_member is False


async def test_every_member_is_counted(uow) -> None:
    community = founded()
    await founded_as(uow, community)
    for _ in range(3):
        await joined_as(uow, community, who=uuid4())

    assert (await uow.communities.get_for(community.id, viewer=None)).member_count == 3


async def test_a_slug_is_taken_only_once_a_community_has_it(uow) -> None:
    community = founded(name="Book Club")

    assert await uow.communities.slug_taken("book-club") is False
    await founded_as(uow, community)
    assert await uow.communities.slug_taken("book-club") is True


async def test_a_second_community_answered_to_by_the_same_slug_is_refused(uow) -> None:
    """Nothing above the repository can reach this: the use case makes a fresh slug
    before it gets here. The key is the last word and it has to be a word."""
    await founded_as(uow, founded(name="Book Club"))
    duplicate = founded(name="Book Club")

    with pytest.raises(ConflictError, match="book-club"):
        await founded_as(uow, duplicate)


# Who belongs.


async def test_a_membership_is_found_by_who_and_which(uow) -> None:
    community = founded()
    member = uuid4()
    await founded_as(uow, community)

    assert await uow.members.find(community_id=community.id, user_id=member) is None

    membership = await joined_as(uow, community, who=member)

    got = await uow.members.find(community_id=community.id, user_id=member)
    assert got is not None
    assert got.id == membership.id
    assert got.community_id == community.id
    assert got.user_id == member
    assert got.joined_at == START
    assert got.pseudonym is None


async def test_a_person_is_one_membership_of_a_community(uow) -> None:
    """A second row for the same pair would be counted twice and joined from twice."""
    community = founded()
    member = uuid4()
    await founded_as(uow, community)
    await joined_as(uow, community, who=member)

    with pytest.raises(ConflictError, match="Already a member"):
        await joined_as(uow, community, who=member)


async def test_a_person_may_belong_to_two_communities(uow) -> None:
    book_club, walkers = (
        founded(name="Book Club"),
        founded(name="Long Distance Walkers", allow_pseudonyms=True),
    )
    member = uuid4()
    await founded_as(uow, book_club, walkers)

    await joined_as(uow, book_club, who=member)
    await joined_as(uow, walkers, who=member, pseudonym="the baker")

    assert (await uow.members.find(community_id=book_club.id, user_id=member)).pseudonym is None
    assert (await uow.members.find(community_id=walkers.id, user_id=member)).pseudonym == (
        "the baker"
    )


async def test_only_the_members_who_chose_a_name_come_back(uow) -> None:
    """The feed asks for a crowd of authors and wants the few who are called something
    else, not a dict with a `None` in it for everyone."""
    community = founded(allow_pseudonyms=True)
    anonymous, named, other = uuid4(), uuid4(), uuid4()
    await founded_as(uow, community)
    await joined_as(uow, community, who=anonymous)
    await joined_as(uow, community, who=named, pseudonym="the baker")

    assert await uow.members.pseudonyms(community_id=community.id, user_ids=[named, other]) == {
        named: "the baker"
    }


async def test_asking_for_no_authors_reads_nothing(uow) -> None:
    """An empty `IN ()` is a syntax error in Postgres, and a feed with no posts on it
    never needs to ask."""
    community = founded()
    await founded_as(uow, community)

    assert await uow.members.pseudonyms(community_id=community.id, user_ids=[]) == {}


async def test_a_pseudonym_stays_in_its_own_community(uow) -> None:
    book_club, walkers = (
        founded(name="Book Club", allow_pseudonyms=True),
        founded(name="Long Distance Walkers"),
    )
    member = uuid4()
    await founded_as(uow, book_club, walkers)
    await joined_as(uow, book_club, who=member, pseudonym="the baker")

    assert await uow.members.pseudonyms(community_id=walkers.id, user_ids=[member]) == {}


# The feed.


async def test_a_community_feed_is_newest_first(uow) -> None:
    community = founded()
    await founded_as(uow, community)
    await said_as(
        uow,
        said(community=community.id, minutes=1),
        said(community=community.id, minutes=9),
        said(community=community.id, minutes=5),
    )

    page = await uow.feed.page(community_id=community.id, before=None, limit=10)

    assert [post.created_at for post in page] == [
        START + timedelta(minutes=9),
        START + timedelta(minutes=5),
        START + timedelta(minutes=1),
    ]


async def test_a_community_feed_is_that_community_only(uow) -> None:
    """Including the posts filed nowhere: those are the locality feed's, and a
    community's members did not ask for them."""
    book_club, walkers = founded(name="Book Club"), founded(name="Long Distance Walkers")
    await founded_as(uow, book_club, walkers)
    await said_as(
        uow,
        said(community=book_club.id),
        said(community=walkers.id),
        said(community=None),
    )

    page = await uow.feed.page(community_id=book_club.id, before=None, limit=10)

    assert len(page) == 1


async def test_a_community_feed_leaves_out_what_was_taken_down(uow) -> None:
    """Everything else the moderation filter keeps: pending, approved and flagged all
    stay, exactly as on the main feed."""
    community = founded()
    await founded_as(uow, community)
    await said_as(
        uow,
        said(community=community.id, minutes=1),
        said(community=community.id, minutes=2, taken_down=True),
    )

    page = await uow.feed.page(community_id=community.id, before=None, limit=10)

    assert len(page) == 1
    assert page[0].moderation_status is not ModerationStatus.REMOVED


async def test_a_community_feed_starts_where_the_last_page_stopped(uow) -> None:
    community = founded()
    await founded_as(uow, community)
    await said_as(uow, *(said(community=community.id, minutes=minute) for minute in range(5)))

    page = await uow.feed.page(community_id=community.id, before=None, limit=2)
    next_page = await uow.feed.page(community_id=community.id, before=page[-1].created_at, limit=2)

    assert [post.created_at for post in page] == [
        START + timedelta(minutes=4),
        START + timedelta(minutes=3),
    ]
    assert [post.created_at for post in next_page] == [
        START + timedelta(minutes=2),
        START + timedelta(minutes=1),
    ]


async def test_a_cursor_written_in_another_zone_still_compares(uow) -> None:
    """A cursor is a timestamp off a phone, and the column is written in UTC: the
    comparison is between instants, not between wall clocks."""
    community = founded()
    await founded_as(uow, community)
    await said_as(
        uow,
        said(community=community.id, minutes=1),
        said(community=community.id, minutes=2),
    )

    page = await uow.feed.page(
        community_id=community.id, before=START + timedelta(minutes=2), limit=10
    )
    same_instant_in_tokyo = (START + timedelta(minutes=2)).astimezone(TOKYO)
    in_tokyo = await uow.feed.page(
        community_id=community.id, before=same_instant_in_tokyo, limit=10
    )

    assert [post.created_at for post in page] == [START + timedelta(minutes=1)]
    assert [post.created_at for post in in_tokyo] == [START + timedelta(minutes=1)]


async def test_a_post_at_the_cursor_is_not_on_the_next_page(uow) -> None:
    """`before` is older than, not up to: a post that was the last one read must not
    come round again."""
    community = founded()
    await founded_as(uow, community)
    last = said(community=community.id, minutes=1)
    await said_as(uow, last, said(community=community.id, minutes=2))

    page = await uow.feed.page(community_id=community.id, before=last.created_at, limit=10)

    assert page == []
