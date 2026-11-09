"""RELY-93: the moderation trail, and the two columns the admin API needs.

`moderation_log` is new: until now nothing wrote down who changed what, so an admin
who removed a post last week could not say why. It is append-only - a row is a fact
that happened, not a setting to be edited.

`users.deactivated_at` is what switching an account off means. A nullable timestamp
rather than a boolean, because "when" is the part an admin is asked for, and because
it leaves the row alone: their posts stay, their handle stays taken, and putting them
back is clearing one column.

`invites.note` is who an invite was set aside for, so a list of open invites is not
a list of anonymous strings.

`moderation_log.trigger` says who made the call - `human` or `ai` - and `ai_decision`
holds what a model said, as it came out. The queue shows both against the same post, so
the admin reads the machine's opinion and the post together. `actor_id` is nullable for
the same reason: a model has no account, and inventing one to fill a column would be the
first lie in a table whose job is telling the truth.

`post_id`, `community_id` and `target_user_id` carry no foreign key on purpose. An
audit row has to outlive the thing it is about: a cascade would let deleting a post
also delete the record of why it was deleted, and a post that is gone is exactly
when somebody starts asking questions. The two `users` references are the exception -
they name the person who was acted on, and an account that has been deleted out from
under a log row is worth the database objecting to.

Revision ID: 0006_moderation
Revises: 0005_replies_reactions
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_moderation"
down_revision: str | None = "0005_replies_reactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _row_id() -> sa.BigInteger:
    """The type of a row number. SQLite only autoincrements INTEGER; Postgres gets BIGINT."""
    return sa.BigInteger().with_variant(sa.Integer, "sqlite")


def upgrade() -> None:
    op.add_column("users", sa.Column("deactivated_at", sa.DateTime(), nullable=True))
    # Who the invite was set aside for. Free text on purpose: it is read by the person
    # holding the list, and never parsed by anything.
    op.add_column("invites", sa.Column("note", sa.String(length=200), nullable=True))
    op.create_table(
        "moderation_log",
        sa.Column("id", _row_id(), primary_key=True),
        # Nullable: a machine decision has no actor behind it.
        sa.Column("actor_id", _row_id(), nullable=True),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("trigger", sa.String(length=12), nullable=False, server_default="human"),
        sa.Column("post_id", sa.Uuid(), nullable=True),
        sa.Column("community_id", sa.Uuid(), nullable=True),
        sa.Column("target_user_id", _row_id(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        # The verdict as it came out of whatever looked at the post. JSON on purpose: the
        # shape belongs to the model that wrote it and this table must not pretend to know
        # it. SQLite stores it as text, Postgres as JSON, and neither cares.
        sa.Column("ai_decision", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name="fk_moderation_log_actor_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"], ["users.id"], name="fk_moderation_log_target_user_id_users"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_moderation_log_created_at"), "moderation_log", ["created_at"], unique=False
    )
    op.create_index(op.f("ix_moderation_log_post_id"), "moderation_log", ["post_id"], unique=False)
    op.create_index(
        op.f("ix_moderation_log_target_user_id"), "moderation_log", ["target_user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_moderation_log_target_user_id"), table_name="moderation_log")
    op.drop_index(op.f("ix_moderation_log_post_id"), table_name="moderation_log")
    op.drop_index(op.f("ix_moderation_log_created_at"), table_name="moderation_log")
    op.drop_table("moderation_log")
    with op.batch_alter_table("invites") as batch_op:
        batch_op.drop_column("note")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("deactivated_at")
