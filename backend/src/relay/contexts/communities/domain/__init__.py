"""Communities domain: a community and where it reaches, being a member, and its feed."""

from relay.contexts.communities.domain.community import (
    DEFAULT_RADIUS_KM,
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MAX_RADIUS_KM,
    MIN_RADIUS_KM,
    Community,
    CommunityError,
    CommunityNotFoundError,
    OutOfRangeError,
    slugify,
)
from relay.contexts.communities.domain.feed import CommunityFeedPage, CommunityPost
from relay.contexts.communities.domain.membership import (
    MAX_PSEUDONYM_LENGTH,
    Membership,
    NotAMemberError,
)
from relay.contexts.communities.domain.ports import (
    CellReach,
    CommunityFeedReader,
    CommunityRepository,
    MembershipRepository,
)

__all__ = [
    "DEFAULT_RADIUS_KM",
    "MAX_DESCRIPTION_LENGTH",
    "MAX_NAME_LENGTH",
    "MAX_PSEUDONYM_LENGTH",
    "MAX_RADIUS_KM",
    "MIN_RADIUS_KM",
    "CellReach",
    "Community",
    "CommunityError",
    "CommunityFeedPage",
    "CommunityFeedReader",
    "CommunityNotFoundError",
    "CommunityPost",
    "CommunityRepository",
    "Membership",
    "MembershipRepository",
    "NotAMemberError",
    "OutOfRangeError",
    "slugify",
]
