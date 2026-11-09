"""The posts table. This model never leaves the infrastructure layer."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from relay.contexts.posts.domain.post import ModerationStatus, Post
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
    Both are plain columns until those contexts land and can add the constraint.
    """

    __tablename__ = "posts"
    # The feed's only query: a cell, then walk it backwards in time.
    __table_args__ = (Index("ix_posts_location_cell_created_at", "location_cell", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    author_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    location_cell: Mapped[str | None] = mapped_column(String(32))
    community_id: Mapped[UUID | None] = mapped_column(Uuid)
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
            moderation_status=ModerationStatus(self.moderation_status),
        )
