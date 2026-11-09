"""The posts tables: what people said, and the emoji they left under it.

These models never leave the infrastructure layer.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from relay.contexts.posts.domain.post import ModerationStatus, Post
from relay.contexts.posts.domain.reaction import MAX_EMOJI_LENGTH, Reaction
from relay.shared.infrastructure.database import Base


def _as_utc(value: datetime) -> datetime:
    """SQLite stores no offset, so a timestamp read back is naive and UTC by agreement.

    Postgres keeps the offset in `timestamptz` and hands back an aware datetime, so
    this is a no-op there. Without it a feed's timestamps would serialise without a
    zone and the client would read them as local time.
    """
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class PostModel(Base):
    """One post.

    `author_id` and `community_id` carry no foreign key on purpose: the users table
    belongs to RELY-87 and the communities table to RELY-89 and neither exists yet.
    Neither does `parent_id`: a post comes down by being marked, not deleted, and a
    reply whose parent is gone is never read - a thread is opened from its parent.
    """

    __tablename__ = "posts"
    # The feed's only query: a cell, then walk it backwards in time.
    __table_args__ = (
        Index("ix_posts_location_cell_created_at", "location_cell", "created_at"),
        # Opening a thread: one post's replies, in the order they were said.
        Index("ix_posts_parent_id_created_at", "parent_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    author_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    location_cell: Mapped[str | None] = mapped_column(String(32))
    community_id: Mapped[UUID | None] = mapped_column(Uuid)
    parent_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    moderation_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ModerationStatus.PENDING.value
    )

    @classmethod
    def from_domain(cls, post: Post) -> "PostModel":
        return cls(
            id=post.id,
            author_id=post.author_id,
            body=post.body,
            location_cell=post.location_cell,
            community_id=post.community_id,
            parent_id=post.parent_id,
            # Stored in UTC whichever zone the post was said in, so what comes back out
            # is the same instant: SQLite keeps no offset of its own to fall back on.
            created_at=post.created_at.astimezone(UTC),
            moderation_status=post.moderation_status.value,
        )

    def to_domain(self) -> Post:
        return Post(
            id=self.id,
            author_id=self.author_id,
            body=self.body,
            created_at=_as_utc(self.created_at),
            location_cell=self.location_cell,
            community_id=self.community_id,
            parent_id=self.parent_id,
            moderation_status=ModerationStatus(self.moderation_status),
        )


class ReactionModel(Base):
    """One person's one emoji on one post.

    `user_id` carries no foreign key for the same reason `author_id` does not: the
    users table is RELY-87's and does not exist yet. `post_id` does, cheaply, because
    this table is new: a reaction left on a post that is deleted has nothing left to
    sit on.
    """

    __tablename__ = "post_reactions"
    __table_args__ = (
        # One person says an emoji once per post, written down here as well as in the
        # service, because two writers arriving at once is the only way it gets said
        # twice. It doubles as the index every read of a post's reactions walks.
        UniqueConstraint("post_id", "user_id", "emoji", name="uq_post_reactions_post_user_emoji"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    post_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    emoji: Mapped[str] = mapped_column(String(MAX_EMOJI_LENGTH), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_domain(cls, reaction: Reaction) -> "ReactionModel":
        return cls(
            id=reaction.id,
            post_id=reaction.post_id,
            user_id=reaction.user_id,
            emoji=reaction.emoji,
            created_at=reaction.created_at.astimezone(UTC),
        )

    def to_domain(self) -> Reaction:
        return Reaction(
            id=self.id,
            post_id=self.post_id,
            user_id=self.user_id,
            emoji=self.emoji,
            created_at=_as_utc(self.created_at),
        )
