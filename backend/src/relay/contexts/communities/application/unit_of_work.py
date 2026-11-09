"""The communities unit of work: one transaction over the communities and members tables."""

from relay.contexts.communities.domain.ports import (
    CommunityFeedReader,
    CommunityRepository,
    MembershipRepository,
)
from relay.shared.application import UnitOfWork


class CommunitiesUnitOfWork(UnitOfWork):
    """A transaction over communities and their members.

    `feed` reads the posts table, which is the posts context's to write: a community
    feed is read out of it and nothing in this context puts anything into it.
    Implementations set all three on entry.
    """

    communities: CommunityRepository
    members: MembershipRepository
    feed: CommunityFeedReader
