"""An event can be filed under a community.

A post already knows how to belong to a community, and an event now does the same thing:
`community_id` says which, and it is nullable, so every event already planned stays
exactly where it was — a place's event, on nobody's community list.

The index is the other list's only query shape, and it is the same shape as the locality
one: a community, then walk it forwards in time from wherever the page starts.

`community_id` gets no foreign key, for the same two reasons the column on `posts` has
none: the communities table belongs to another context, which is allowed to read events
and never to be depended on by them.

Revision ID: 0007_event_communities
Revises: 0006_moderation
Create Date: 2026-11-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_event_communities"
down_revision: str | None = "0006_moderation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("events", sa.Column("community_id", sa.Uuid(), nullable=True))
    op.create_index(
        "ix_events_community_id_starts_at", "events", ["community_id", "starts_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_events_community_id_starts_at", table_name="events")
    op.drop_column("events", "community_id")
