"""Being a member: who joined which community, and under what name."""

from datetime import datetime
from uuid import UUID

from relay.contexts.communities.domain.community import Community, CommunityError
from relay.shared.domain import Entity, ValidationError

#: The same ceiling the join sheet counts down from (MAX_PSEUDONYM_LENGTH in
#: mobile/src/domain/community.ts). Short on purpose: it goes next to every post the
#: member writes, in a list, on a phone.
MAX_PSEUDONYM_LENGTH = 40


class NotAMemberError(CommunityError):
    """A community's feed is for its members, and this reader is not one of them."""


class Membership(Entity):
    """One person's membership of one community.

    `pseudonym` is what this member is called *here* and nowhere else: the same person
    is "Ana" in one community and "not-the-councillor" in the next. It is set when
    they join and is not this context's to change afterwards.
    """

    community_id: UUID
    user_id: UUID
    pseudonym: str | None = None
    joined_at: datetime

    @classmethod
    def join(
        cls,
        community: Community,
        *,
        user_id: UUID,
        joined_at: datetime,
        pseudonym: str | None = None,
    ) -> "Membership":
        """Record `user_id` as a member of `community`.

        Joining a second time is not this factory's problem: `JoinCommunity` hands back
        the membership that already exists and never calls this twice.

        A pseudonym is refused rather than dropped when the community does not allow
        them. Someone who asked to be anonymous and was quietly named is worse off
        than one who got an error, and the client already hides the field for a
        community that does not allow them (`allowPseudonyms` in
        mobile/src/domain/community.ts), so nobody sends one by accident.
        """
        chosen = pseudonym.strip() if pseudonym else ""
        if chosen and not community.allow_pseudonyms:
            raise ValidationError(f"{community.name} does not let members use a pseudonym.")
        if len(chosen) > MAX_PSEUDONYM_LENGTH:
            raise ValidationError(f"A pseudonym is at most {MAX_PSEUDONYM_LENGTH} characters.")
        return cls(
            community_id=community.id,
            user_id=user_id,
            joined_at=joined_at,
            pseudonym=chosen or None,
        )
