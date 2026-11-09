"""The events and rsvps tables. These models never leave the infrastructure layer."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from relay.contexts.events.domain.event import MAX_TITLE_LENGTH, MAX_VENUE_LENGTH, Event
from relay.contexts.events.domain.rsvp import Rsvp
from relay.shared.infrastructure.database import Base


def _as_utc(value: datetime) -> datetime:
    """SQLite stores no offset, so a timestamp read back is naive and UTC by agreement.

    Postgres keeps the offset in `timestamptz` and hands back an aware datetime, so
    this is a no-op there. Without it an event's start time would serialise without a
    zone and the client would read it as local time.
    """
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class EventModel(Base):
    """One event.

    `host_id` carries no foreign key on purpose: the users table belongs to RELY-87
    and does not exist yet, so it is a plain column until that context can add the
    constraint. `location_cell` does the job it does on a post — it is what puts the
    event in a locality's list of what is on.
    """

    __tablename__ = "events"
    # The list's only query: a cell, then walk it forward in time.
    __table_args__ = (Index("ix_events_location_cell_starts_at", "location_cell", "starts_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    host_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(String(MAX_TITLE_LENGTH), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    venue_name: Mapped[str | None] = mapped_column(String(MAX_VENUE_LENGTH))
    details: Mapped[str | None] = mapped_column(Text)
    location_cell: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_domain(cls, event: Event) -> "EventModel":
        return cls(
            id=event.id,
            host_id=event.host_id,
            title=event.title,
            # Stored in UTC whichever zone the time was named in, so what comes back
            # out is the same instant: SQLite keeps no offset of its own to fall back on.
            starts_at=event.starts_at.astimezone(UTC),
            ends_at=None if event.ends_at is None else event.ends_at.astimezone(UTC),
            venue_name=event.venue_name,
            details=event.details,
            location_cell=event.location_cell,
            created_at=event.created_at.astimezone(UTC),
        )

    def to_domain(self) -> Event:
        return Event(
            id=self.id,
            host_id=self.host_id,
            title=self.title,
            starts_at=_as_utc(self.starts_at),
            ends_at=None if self.ends_at is None else _as_utc(self.ends_at),
            venue_name=self.venue_name,
            details=self.details,
            location_cell=self.location_cell,
            created_at=_as_utc(self.created_at),
        )


class RsvpModel(Base):
    """One member's place at one event.

    The foreign key is real, unlike the one to a host: this table and `events` both
    belong to the events context, so the constraint can be enforced today. An event
    deleted takes the places taken at it with them, because a place at nothing is not
    a place. The unique pair is what makes saying you are going twice say it once.
    """

    __tablename__ = "rsvps"
    __table_args__ = (
        UniqueConstraint("event_id", "member_id", name="uq_rsvps_event_id_member_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_domain(cls, rsvp: Rsvp) -> "RsvpModel":
        return cls(
            id=rsvp.id,
            event_id=rsvp.event_id,
            member_id=rsvp.member_id,
            created_at=rsvp.created_at.astimezone(UTC),
        )

    def to_domain(self) -> Rsvp:
        return Rsvp(
            id=self.id,
            event_id=self.event_id,
            member_id=self.member_id,
            created_at=_as_utc(self.created_at),
        )
