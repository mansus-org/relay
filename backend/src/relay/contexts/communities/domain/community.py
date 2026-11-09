"""A community: people who share a place, a subject, or both."""

import re
import unicodedata
from datetime import datetime
from uuid import UUID

from relay.shared.domain import DomainError, Entity, ValidationError

#: The same ceiling the create screen counts down from (MAX_COMMUNITY_NAME_LENGTH in
#: mobile/src/domain/community.ts), so a name the client allows is a name the server keeps.
MAX_NAME_LENGTH = 80

#: No counter on the client, so this is the ceiling it gets: the length a post body is
#: allowed, which is the one paragraph length Relay already has a number for.
MAX_DESCRIPTION_LENGTH = 500

#: How far a community reaches from the cell it is anchored at. Both numbers are the
#: create screen's (MIN/MAX_COMMUNITY_RADIUS_KM in mobile/src/domain/community.ts).
#: A community too small to reach the shop next door is not a locality, and one big
#: enough to cover a province is a region and wants being several communities instead.
MIN_RADIUS_KM = 1.0
MAX_RADIUS_KM = 50.0
DEFAULT_RADIUS_KM = 5.0

#: Long enough for any name worth slugging, short enough to stay one URL segment.
MAX_SLUG_LENGTH = 64


class CommunityError(DomainError):
    """Base class for the ways a community can fail to be joinable."""


class OutOfRangeError(CommunityError):
    """The reader is standing too far from the community to join it."""


class CommunityNotFoundError(DomainError):
    """There is no community to show under that id."""


def slugify(name: str) -> str:
    """`name` as a slug: lower case, plain ASCII, hyphens where the punctuation was.

    Returns "" for a name with nothing letterlike in it, and the caller has to fall
    back to something else: an empty slug would be shared by every community named
    "!!!" after the first one.
    """
    flattened = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    words = re.split(r"[^a-z0-9]+", flattened.lower())
    return "-".join(word for word in words if word)[:MAX_SLUG_LENGTH].strip("-")


class Community(Entity):
    """One community.

    `location_cell` and `radius_km` together are its locality: the cell it is anchored
    at and how far out that anchor reaches. Either can be absent, and a community with
    no anchor is a community about a subject rather than a place — it exists, anyone
    who finds a link to it can join it, and it is in nobody's nearby list.

    How far a cell is from the anchor is geometry, and the domain does not do geometry
    (see `CellReach`): `ListCommunities` and `JoinCommunity` ask a reach about
    `location_cell` and `radius_km` and never work out a distance themselves.
    """

    name: str
    slug: str
    description: str = ""
    location_cell: str | None = None
    radius_km: float | None = None
    allow_pseudonyms: bool = False
    created_by: UUID
    created_at: datetime

    #: Both of these come out of the members table when a repository loads a community,
    #: and neither is state a community carries: `member_count` counts rows, and
    #: `is_member` answers a question about whoever asked. They are 0 and False on a
    #: community that has just been founded, because nobody has joined it yet.
    member_count: int = 0
    is_member: bool = False

    @classmethod
    def start(
        cls,
        *,
        name: str,
        created_by: UUID,
        created_at: datetime,
        description: str = "",
        location_cell: str | None = None,
        radius_km: float | None = None,
        allow_pseudonyms: bool = False,
        slug: str | None = None,
    ) -> "Community":
        """The one way a community is founded, so nothing is saved unnameable.

        A radius with no cell to measure it from is dropped rather than refused: the
        create screen always sends its default radius, and a community that did not
        say where it is has no reach to store either way.
        """
        called = name.strip()
        if not called:
            raise ValidationError("A community needs a name.")
        if len(called) > MAX_NAME_LENGTH:
            raise ValidationError(f"A community name is at most {MAX_NAME_LENGTH} characters.")
        said = description.strip()
        if len(said) > MAX_DESCRIPTION_LENGTH:
            raise ValidationError(
                f"A community description is at most {MAX_DESCRIPTION_LENGTH} characters."
            )
        anchored = location_cell.strip() if location_cell else ""
        return cls(
            name=called,
            slug=slug or slugify(called) or f"c-{str(created_by)[:8]}",
            description=said,
            location_cell=anchored or None,
            radius_km=_reaches(radius_km) if anchored else None,
            allow_pseudonyms=allow_pseudonyms,
            created_by=created_by,
            created_at=created_at,
        )

    @property
    def is_anchored(self) -> bool:
        """Whether this community is somewhere, and so somebody's nearby list."""
        return self.location_cell is not None and self.radius_km is not None


def _reaches(radius_km: float | None) -> float:
    if radius_km is None:
        return DEFAULT_RADIUS_KM
    if not MIN_RADIUS_KM <= radius_km <= MAX_RADIUS_KM:
        raise ValidationError(
            f"A community's radius is between {MIN_RADIUS_KM} and {MAX_RADIUS_KM} km."
        )
    return radius_km
