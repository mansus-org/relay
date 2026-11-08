"""Accounts, invites and sessions: the tables auth needs.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _row_id() -> sa.types.TypeEngine:
    """The type of a row number. SQLite only autoincrements INTEGER; Postgres gets BIGINT."""
    return sa.BigInteger().with_variant(sa.Integer, "sqlite")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", _row_id(), primary_key=True),
        sa.Column("username", sa.String(20), nullable=False),
        sa.Column("display_name", sa.String(60), nullable=False),
        # A bcrypt string is 60 characters; the room is for whatever replaces bcrypt.
        sa.Column("password_hash", sa.String(120), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )

    op.create_table(
        "invites",
        sa.Column("id", _row_id(), primary_key=True),
        # The whole secret of an invite: 43 characters of urlsafe random, never decoded.
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("created_by_id", _row_id(), nullable=True),
        sa.Column("used_by_id", _row_id(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name="fk_invites_created_by_id_users"
        ),
        sa.ForeignKeyConstraint(["used_by_id"], ["users.id"], name="fk_invites_used_by_id_users"),
        sa.UniqueConstraint("token", name="uq_invites_token"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", _row_id(), primary_key=True),
        sa.Column("user_id", _row_id(), nullable=False),
        # A sha256 of the token, never the token: these rows must not be replayable as sessions.
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_refresh_tokens_user_id_users"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    # Every refresh is a lookup by fingerprint, and every cleanup is a scan by expiry.
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("invites")
    op.drop_table("users")
