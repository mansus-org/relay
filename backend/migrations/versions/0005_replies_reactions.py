"""Replies and reactions: what people say under a post, and the emoji they leave on it.

A reply is a post with `parent_id` set to the post it answers, so a thread is the same
table read one level at a time and needs no new shape. The new index is the one query
that opens a thread: one parent, then its replies forwards in time.

Reactions are their own table, because one post carries many emoji from many people and
a column would have to be a list. One row is one person's one emoji on one post, and the
key that says so is also the index every tally reads. `user_id` gets no foreign key: the
users table is RELY-87's and does not exist yet. Neither does `parent_id`: a post comes
down by being marked, not deleted, and a reply whose parent is gone is never read - a
thread is opened from its parent.

Revision ID: 0005_replies_reactions
Revises: 0005_auth
Create Date: 2026-11-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_replies_reactions"
down_revision: str | None = "0005_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("parent_id", sa.Uuid(), nullable=True))
    op.create_index(
        "ix_posts_parent_id_created_at", "posts", ["parent_id", "created_at"], unique=False
    )
    op.create_table(
        "post_reactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("emoji", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_post_reactions")),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
            name=op.f("fk_post_reactions_post_id_posts"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "post_id", "user_id", "emoji", name="uq_post_reactions_post_user_emoji"
        ),
    )


def downgrade() -> None:
    op.drop_table("post_reactions")
    op.drop_index("ix_posts_parent_id_created_at", table_name="posts")
    op.drop_column("posts", "parent_id")
