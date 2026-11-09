"""Communities, and who belongs to each one.

Two tables. `communities` is a group of people, either about something or somewhere:
`location_cell` and `radius_km` are the somewhere and are both null for a community
that is only about something, which is what keeps it out of every nearby list without
needing a flag for it. `community_members` is the membership itself, and `pseudonym`
lives on the membership and not on the person, because being "the baker" here says
nothing about who you are anywhere else.

`communities.created_by` and `community_members.user_id` carry no foreign key: the
users table is RELY-87's and does not exist yet. `community_members.community_id`
does have one, because its table is in this migration and can.

`posts.community_id` gets no foreign key either, though it now points here for real.
SQLite cannot add one to a table that already exists without rebuilding it, and a
constraint that holds on Postgres and not on the database every test runs against is
worse than none: it would let a test pass that production would fail. The posts
context can add it itself, in its model and its migration, when it next touches that
table.

Revision ID: 0003_communities
Revises: 0002_posts
Create Date: 2026-11-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_communities"
down_revision: str | None = "0002_posts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "communities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location_cell", sa.String(length=32), nullable=True),
        sa.Column("radius_km", sa.Float(), nullable=True),
        sa.Column("allow_pseudonyms", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_communities")),
        # Two towns can each have a Book Club; they cannot both own the slug.
        sa.UniqueConstraint("slug", name=op.f("uq_communities_slug")),
    )
    op.create_table(
        "community_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("community_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("pseudonym", sa.String(length=40), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_community_members")),
        sa.ForeignKeyConstraint(
            ["community_id"],
            ["communities.id"],
            name=op.f("fk_community_members_community_id_communities"),
        ),
        # One person is one membership of a community, and is counted in it once.
        sa.UniqueConstraint(
            "community_id", "user_id", name=op.f("uq_community_members_community_id")
        ),
    )


def downgrade() -> None:
    op.drop_table("community_members")
    op.drop_table("communities")
