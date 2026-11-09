"""The events and rsvps tables.

An event is a what, a when and a where: `location_cell` is the same resolution-8 H3
cell a post is filed under, and it is what puts the event in a locality's list of what
is on. The index is that list's only query shape — a cell, then walk it forwards in
time — so it is composite and in that order.

`host_id` gets no foreign key: the users table is RELY-87's and does not exist yet.
`rsvps.event_id` does, because both tables belong to this context: one row per member
per event, and the unique pair is what makes saying you are going twice say it once.

Revision ID: 0004_events
Revises: 0003_communities
Create Date: 2026-11-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_events"
down_revision: str | None = "0003_communities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("venue_name", sa.String(length=200), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("location_cell", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    op.create_index(
        "ix_events_location_cell_starts_at", "events", ["location_cell", "starts_at"], unique=False
    )
    op.create_table(
        "rsvps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rsvps")),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_rsvps_event_id_events"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("event_id", "member_id", name=op.f("uq_rsvps_event_id_member_id")),
    )


def downgrade() -> None:
    op.drop_table("rsvps")
    op.drop_index("ix_events_location_cell_starts_at", table_name="events")
    op.drop_table("events")
