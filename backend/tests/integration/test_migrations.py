from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.shared.infrastructure.database import create_session_factory
from relay.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


def test_the_migrations_are_one_line_and_not_a_fork() -> None:
    """Twice now two branches have each landed a migration on the same parent, and
    alembic only says so when the second one merges. It is cheaper to say it here.
    """
    ini = Path(__file__).parents[2] / "alembic.ini"
    heads = ScriptDirectory.from_config(Config(str(ini))).get_heads()
    assert len(heads) == 1, f"the migration chain has forked: {heads}"


async def test_upgrade_head_records_revision(migrated_engine: AsyncEngine) -> None:
    async with migrated_engine.connect() as conn:
        version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
    assert version == "0007_event_communities"


async def test_upgrade_creates_the_auth_tables(migrated_engine: AsyncEngine) -> None:
    """An empty Relay still has somewhere to put its first account."""

    def tables(sync_conn: Connection) -> set[str]:
        return set(inspect(sync_conn).get_table_names())

    async with migrated_engine.connect() as conn:
        names: set[str] = await conn.run_sync(tables)
    assert {"users", "invites", "refresh_tokens"} <= names


async def test_unit_of_work_runs_a_query(migrated_engine: AsyncEngine) -> None:
    uow = SqlAlchemyUnitOfWork(create_session_factory(migrated_engine))
    async with uow:
        assert (await uow.session.execute(text("SELECT 1"))).scalar_one() == 1
        await uow.commit()


async def test_the_posts_table_is_there_with_the_columns_the_feed_needs(
    migrated_engine: AsyncEngine,
) -> None:
    async with migrated_engine.connect() as conn:
        columns = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_columns("posts"))

    assert {column["name"] for column in columns} == {
        "id",
        "author_id",
        "body",
        "location_cell",
        "community_id",
        "created_at",
        "moderation_status",
        "parent_id",
    }
    # Only the locality, the community and the post it answers are optional; the rest is
    # required.
    assert {column["name"] for column in columns if not column["nullable"]} == {
        "id",
        "author_id",
        "body",
        "created_at",
        "moderation_status",
    }


async def test_the_thread_index_walks_the_parent_then_the_clock(
    migrated_engine: AsyncEngine,
) -> None:
    """Opening a thread is one parent, then its replies in the order they were said."""
    async with migrated_engine.connect() as conn:
        indexes = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_indexes("posts"))

    thread = next(index for index in indexes if index["name"] == "ix_posts_parent_id_created_at")
    assert thread["column_names"] == ["parent_id", "created_at"]


async def test_the_reactions_table_holds_one_emoji_per_person_per_post(
    migrated_engine: AsyncEngine,
) -> None:
    async with migrated_engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_columns("post_reactions")
        )
        constraints = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_unique_constraints("post_reactions")
        )

    assert {column["name"] for column in columns} == {
        "id",
        "post_id",
        "user_id",
        "emoji",
        "created_at",
    }
    assert all(not column["nullable"] for column in columns)
    # The one rule the table exists to hold: one person, one emoji, one post.
    assert [sorted(one["column_names"]) for one in constraints] == [["emoji", "post_id", "user_id"]]


async def test_the_feed_index_walks_the_cell_then_the_clock(
    migrated_engine: AsyncEngine,
) -> None:
    """The one index the feed query needs, and in that order: cell first, then time."""
    async with migrated_engine.connect() as conn:
        indexes = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_indexes("posts"))

    feed = next(index for index in indexes if index["name"] == "ix_posts_location_cell_created_at")
    assert feed["column_names"] == ["location_cell", "created_at"]


async def test_the_events_table_is_there_with_the_columns_a_listing_needs(
    migrated_engine: AsyncEngine,
) -> None:
    async with migrated_engine.connect() as conn:
        columns = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_columns("events"))

    assert {column["name"] for column in columns} == {
        "id",
        "host_id",
        "title",
        "starts_at",
        "ends_at",
        "venue_name",
        "details",
        "location_cell",
        "community_id",
        "created_at",
    }
    # Where and when it ends are the host's to leave out; what and when it starts are not.
    # Which community it belongs to is theirs to leave out too: a plan can be a place's
    # and nobody's group.
    assert {column["name"] for column in columns if not column["nullable"]} == {
        "id",
        "host_id",
        "title",
        "starts_at",
        "created_at",
    }


async def test_the_events_index_walks_the_cell_then_the_clock(
    migrated_engine: AsyncEngine,
) -> None:
    """A list of what is on is one query: this cell, then forward in time."""
    async with migrated_engine.connect() as conn:
        indexes = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_indexes("events"))

    listing = next(
        index for index in indexes if index["name"] == "ix_events_location_cell_starts_at"
    )
    assert listing["column_names"] == ["location_cell", "starts_at"]


async def test_the_events_index_walks_the_community_then_the_clock(
    migrated_engine: AsyncEngine,
) -> None:
    """A community's list is the same one query with the other column first: this
    community, then forward in time from wherever the page starts.
    """
    async with migrated_engine.connect() as conn:
        indexes = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_indexes("events"))

    listing = next(
        index for index in indexes if index["name"] == "ix_events_community_id_starts_at"
    )
    assert listing["column_names"] == ["community_id", "starts_at"]


async def test_a_place_is_taken_against_one_event_and_one_member_once(
    migrated_engine: AsyncEngine,
) -> None:
    """The pair that makes saying you are going twice say it once, in the schema."""
    async with migrated_engine.connect() as conn:
        columns = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_columns("rsvps"))
        uniques = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_unique_constraints("rsvps")
        )
        keys = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_foreign_keys("rsvps"))

    assert {column["name"] for column in columns} == {
        "id",
        "event_id",
        "member_id",
        "created_at",
    }
    assert {tuple(constraint["column_names"]) for constraint in uniques} == {
        ("event_id", "member_id")
    }
    assert [(key["referred_table"], key["options"].get("ondelete")) for key in keys] == [
        ("events", "CASCADE")
    ]
