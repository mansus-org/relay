"""The community an event is filed under, as far as this context is allowed to know it.

An event reaches a locality through its cell and a community through `community_id`, and
the communities context owns everything else about that community: what it is called, who
is in it, how far its reach goes. This context reads those and never writes them, so the
dependency between the two contexts points one way and the same way everywhere.
"""

from relay.shared.domain import DomainError


class CommunityError(DomainError):
    """Base class for the ways an event can fail to belong to a community."""


class CommunityNotFoundError(CommunityError):
    """There is no community to file an event under, or to show the events of."""


class NotAMemberError(CommunityError):
    """The host is not in the community they tried to file an event under.

    Filing an event under a community puts it on that community's list, where every one
    of its members will see it. Only its members get to put something there.
    """
