"""A post: something someone said, and where in Relay it was said."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from relay.shared.domain import Entity, NotFoundError, ValidationError

#: The same ceiling the compose screen counts down from (MAX_POST_LENGTH in
#: mobile/src/domain/post.ts), so a body the client allows is a body the server keeps.
MAX_BODY_LENGTH = 500


class ModerationStatus(StrEnum):
    """Where a post stands with moderation.

    Moderation itself is another context's work; the only rule this one has to honour
    is that a removed post stops reaching people.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REMOVED = "removed"


class PostNotFoundError(NotFoundError):
    """There is no post to show under that id."""


class Post(Entity):
    """One post.

    `location_cell` is what puts it in a locality feed and `community_id` what puts it
    in a community's. A post with neither exists but reaches no feed; that is the
    author's problem, not a reason to refuse the write.

    A post that answers another one is a reply, and a reply is only a post with a
    `parent_id`. How deep a thread is drawn is the client's business.
    """

    author_id: UUID
    body: str
    created_at: datetime
    location_cell: str | None = None
    community_id: UUID | None = None
    parent_id: UUID | None = None
    moderation_status: ModerationStatus = ModerationStatus.PENDING

    @classmethod
    def write(
        cls,
        *,
        author_id: UUID,
        body: str,
        created_at: datetime,
        location_cell: str | None = None,
        community_id: UUID | None = None,
        parent_id: UUID | None = None,
    ) -> "Post":
        """The one way a new post is made, so nothing gets saved without being said."""
        said = body.strip()
        if not said:
            raise ValidationError("A post needs some text.")
        if len(said) > MAX_BODY_LENGTH:
            raise ValidationError(f"A post is at most {MAX_BODY_LENGTH} characters.")
        return cls(
            author_id=author_id,
            body=said,
            created_at=created_at,
            location_cell=location_cell or None,
            community_id=community_id,
            parent_id=parent_id,
        )

    @property
    def is_up(self) -> bool:
        """Whether moderation has left the post standing.

        A removed post is still stored and reaches nobody: not the feed, not a thread,
        not a reaction.
        """
        return self.moderation_status is not ModerationStatus.REMOVED

    @property
    def shows_in_locality_feed(self) -> bool:
        """A post reaches the locality feed only when it has a cell and is still up.

        The query enforces the same two conditions in SQL; this is the rule in one
        place for everything that is not the database.
        """
        return self.location_cell is not None and self.is_up

    def removed(self) -> "Post":
        """This post as moderation left it: still stored, reaching nobody."""
        return self.model_copy(update={"moderation_status": ModerationStatus.REMOVED})
