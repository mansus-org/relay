"""The moderation trail table. Nothing outside this package touches it."""

from datetime import UTC, datetime
from typing import overload
from uuid import UUID

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from relay.contexts.admin.domain.moderation_log import (
    ModerationAction,
    ModerationLog,
    ModerationTrigger,
)
from relay.shared.infrastructure.database import Base


def _row_id(*, nullable: bool = False) -> Mapped[int]:
    """A row number in the users table. SQLite only autoincrements INTEGER, so the type
    has to follow the database; everywhere else it is a bigint."""
    return mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=nullable
    )


def _utc() -> Mapped[datetime]:
    """A timestamp column that carries no offset: every one of these is UTC."""
    return mapped_column(DateTime())


@overload
def naive_utc(value: datetime) -> datetime: ...


@overload
def naive_utc(value: None) -> None: ...


def naive_utc(value: datetime | None) -> datetime | None:
    """Drop the offset on the way in: these columns are UTC with no offset to carry."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def aware_utc(value: datetime) -> datetime:
    """Put the offset back on the way out, so the domain only ever sees aware UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class ModerationLogRow(Base):
    """One decision moderation made. Rows are written and read; nothing updates them."""

    __tablename__ = "moderation_log"
    __table_args__ = (
        # The two ways this table gets asked about: everything that happened to one
        # thing, and everything that happened lately.
        Index("ix_moderation_log_created_at", "created_at"),
        Index("ix_moderation_log_post_id", "post_id"),
        Index("ix_moderation_log_target_user_id", "target_user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    # Nullable because a machine decision has nobody behind it.
    actor_id: Mapped[int | None] = _row_id(nullable=True)
    action: Mapped[str] = mapped_column(String(24))
    trigger: Mapped[str] = mapped_column(String(12), default=ModerationTrigger.HUMAN.value)
    post_id: Mapped[UUID | None] = mapped_column(Uuid)
    community_id: Mapped[UUID | None] = mapped_column(Uuid)
    target_user_id: Mapped[int | None] = _row_id()
    reason: Mapped[str] = mapped_column(Text, default="")
    ai_decision: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = _utc()

    @classmethod
    def from_domain(cls, entry: ModerationLog) -> "ModerationLogRow":
        return cls(
            id=entry.id,
            actor_id=entry.actor_id,
            action=entry.action.value,
            trigger=entry.trigger.value,
            post_id=entry.post_id,
            community_id=entry.community_id,
            target_user_id=entry.target_user_id,
            reason=entry.reason,
            ai_decision=entry.ai_decision,
            created_at=naive_utc(entry.created_at),
        )

    def to_domain(self) -> ModerationLog:
        return ModerationLog(
            id=self.id,
            actor_id=self.actor_id,
            action=ModerationAction(self.action),
            trigger=ModerationTrigger(self.trigger),
            post_id=self.post_id,
            community_id=self.community_id,
            target_user_id=self.target_user_id,
            reason=self.reason,
            ai_decision=self.ai_decision,
            created_at=aware_utc(self.created_at),
        )
