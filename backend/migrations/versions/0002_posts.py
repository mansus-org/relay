"""The posts table.

One table for everything anyone says: a `location_cell` puts a post in a locality's
feed, a `community_id` puts it in a community's, and neither is required. The index is
the feed's only query shape — a cell, then walk it backwards in time — so it is
composite and in that order.

`author_id` and `community_id` get no foreign keys: the users table is RELY-87's and
the communities table RELY-89's, and neither exists yet.

Revision ID: 0002_posts
Revises: 0001
Create Date: 2026-11-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_posts"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("location_cell", sa.String(length=32), nullable=True),
        sa.Column("community_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "moderation_status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_posts")),
    )
    op.create_index(
        "ix_posts_location_cell_created_at", "posts", ["location_cell", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_posts_location_cell_created_at", table_name="posts")
    op.drop_table("posts")
