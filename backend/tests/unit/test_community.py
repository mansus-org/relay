"""What makes a community a community: a name, somewhere it reaches, and who may be anonymous."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from relay.contexts.communities.domain.community import (
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MAX_SLUG_LENGTH,
    Community,
    slugify,
)
from relay.contexts.communities.domain.membership import (
    MAX_PSEUDONYM_LENGTH,
    Membership,
)
from relay.shared.domain import ValidationError

NOW = datetime(2026, 3, 4, 12, tzinfo=UTC)


def founded(**fields: Any) -> Community:
    return Community.start(created_by=uuid4(), created_at=NOW, **fields)


def a_community(**fields: Any) -> Community:
    return founded(**{"name": "Vigo Book Club", **fields})


# A name.


def test_a_community_keeps_what_it_was_founded_as() -> None:
    founder = uuid4()
    community = Community.start(
        name="Vigo Book Club",
        description="Second Tuesday, the bakery.",
        created_by=founder,
        created_at=NOW,
    )

    assert community.name == "Vigo Book Club"
    assert community.description == "Second Tuesday, the bakery."
    assert community.created_by == founder
    assert community.created_at == NOW
    assert community.allow_pseudonyms is False
    # Nobody has joined a community at the moment it is founded.
    assert (community.member_count, community.is_member) == (0, False)


def test_the_spaces_around_a_name_are_not_part_of_it() -> None:
    assert a_community(name="  O Camiño  ").name == "O Camiño"


@pytest.mark.parametrize("name", ["", "   ", "\n\t"])
def test_nothing_to_call_it_by_is_no_community(name: str) -> None:
    with pytest.raises(ValidationError, match="needs a name"):
        founded(name=name)


def test_a_name_fits_exactly_what_the_create_screen_allows() -> None:
    longest = "a" * MAX_NAME_LENGTH
    assert a_community(name=longest).name == longest


def test_one_character_over_is_refused_with_the_limit_in_the_message() -> None:
    with pytest.raises(ValidationError, match=str(MAX_NAME_LENGTH)):
        a_community(name="a" * (MAX_NAME_LENGTH + 1))


def test_a_description_fits_what_a_post_body_fits() -> None:
    assert a_community(description="a" * MAX_DESCRIPTION_LENGTH).description == (
        "a" * MAX_DESCRIPTION_LENGTH
    )


def test_a_description_one_over_is_refused_with_the_limit_in_the_message() -> None:
    with pytest.raises(ValidationError, match=str(MAX_DESCRIPTION_LENGTH)):
        a_community(description="a" * (MAX_DESCRIPTION_LENGTH + 1))


# Somewhere it reaches.


def test_a_community_anchored_somewhere_reaches_the_default_distance() -> None:
    """The create screen sends a radius either way, but a caller that does not is not
    left with a community that reaches nowhere."""
    community = a_community(location_cell="883920cd1bfffff")

    assert community.location_cell == "883920cd1bfffff"
    assert community.radius_km == 5.0
    assert community.is_anchored is True


def test_a_community_nowhere_has_no_distance_to_measure() -> None:
    """A radius with no anchor is dropped, not refused: the create screen always sends
    its default, and a community about a subject has no reach to store either way."""
    community = a_community(radius_km=5)

    assert community.location_cell is None
    assert community.radius_km is None
    assert community.is_anchored is False


@pytest.mark.parametrize("radius", [0.9, 0, -5, 50.1, 500])
def test_a_community_too_small_or_too_big_to_be_a_place_is_refused(radius: float) -> None:
    with pytest.raises(ValidationError, match="between"):
        a_community(location_cell="883920cd1bfffff", radius_km=radius)


@pytest.mark.parametrize("radius", [1.0, 50.0])
def test_both_ends_of_the_reach_are_allowed(radius: float) -> None:
    assert a_community(location_cell="883920cd1bfffff", radius_km=radius).radius_km == radius


# The slug.


def test_the_slug_is_the_name_in_lower_case_ascii_with_hyphens() -> None:
    assert slugify("  O Camiño — Vigo!  ") == "o-camino-vigo"
    assert slugify("Book Club") == "book-club"


def test_a_name_with_nothing_letterlike_in_it_slugs_to_nothing() -> None:
    """Not a bug to fix here: `Community.start` falls back to something unique, and it
    can only do that if it can tell an empty slug from a real one."""
    assert slugify("!!!") == ""
    assert slugify("   ") == ""


def test_a_long_name_is_cut_at_a_whole_word() -> None:
    slug = slugify("The Vigo Association of Long Distance Walkers and Their Friends, Founded 1974")

    assert len(slug) <= MAX_SLUG_LENGTH
    assert not slug.endswith("-")


def test_a_community_with_nothing_letterlike_in_its_name_still_gets_a_slug() -> None:
    """A slug is a unique key; the empty string would be shared by every "!!!"."""
    assert a_community(name="!!!").slug != ""


def test_the_fallback_slug_is_the_founder_so_the_use_case_has_to_split_duplicates() -> None:
    """Two "!!!"s by the same founder fall back to the same slug, and `CreateCommunity`
    is what notices and tells them apart by id."""
    founder = uuid4()
    first = Community.start(name="!!!", created_by=founder, created_at=NOW)
    second = Community.start(name="!!!", created_by=founder, created_at=NOW)

    assert first.slug == second.slug


# Being a member.


def test_joining_records_who_joined_where_and_when() -> None:
    community = a_community()
    member = uuid4()
    membership = Membership.join(community, user_id=member, joined_at=NOW)

    assert membership.community_id == community.id
    assert membership.user_id == member
    assert membership.joined_at == NOW
    assert membership.pseudonym is None


def test_a_blank_pseudonym_is_no_pseudonym() -> None:
    assert (
        Membership.join(a_community(), user_id=uuid4(), joined_at=NOW, pseudonym="  ").pseudonym
        is None
    )


def test_a_pseudonym_where_they_are_not_allowed_is_refused_by_name() -> None:
    """Asking not to be named and being named anyway is worse than an error, so this is
    refused rather than quietly dropped."""
    with pytest.raises(ValidationError, match="Vigo Book Club does not let members"):
        Membership.join(a_community(), user_id=uuid4(), joined_at=NOW, pseudonym="the baker")


def test_a_pseudonym_fits_what_the_join_sheet_allows() -> None:
    community = a_community(allow_pseudonyms=True)
    chosen = "a" * MAX_PSEUDONYM_LENGTH

    assert Membership.join(
        community, user_id=uuid4(), joined_at=NOW, pseudonym=chosen
    ).pseudonym == (chosen)


def test_a_pseudonym_one_over_is_refused_with_the_limit_in_the_message() -> None:
    community = a_community(allow_pseudonyms=True)

    with pytest.raises(ValidationError, match=str(MAX_PSEUDONYM_LENGTH)):
        Membership.join(
            community, user_id=uuid4(), joined_at=NOW, pseudonym="a" * (MAX_PSEUDONYM_LENGTH + 1)
        )


def test_a_pseudonym_is_stripped_of_the_spaces_around_it() -> None:
    community = a_community(allow_pseudonyms=True)

    assert (
        Membership.join(
            community, user_id=uuid4(), joined_at=NOW, pseudonym=" the baker "
        ).pseudonym
        == "the baker"
    )
