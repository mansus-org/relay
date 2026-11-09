from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.shared.infrastructure.database import create_session_factory
from relay.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


async def test_upgrade_head_records_revision(migrated_engine: AsyncEngine) -> None:
    async with migrated_engine.connect() as conn:
        version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
    assert version == "0002_posts"


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
    }
    # Only the locality and the community are optional; everything else is required.
    assert {column["name"] for column in columns if not column["nullable"]} == {
        "id",
        "author_id",
        "body",
        "created_at",
        "moderation_status",
    }


async def test_the_feed_index_walks_the_cell_then_the_clock(
    migrated_engine: AsyncEngine,
) -> None:
    """The one index the feed query needs, and in that order: cell first, then time."""
    async with migrated_engine.connect() as conn:
        indexes = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_indexes("posts"))

    feed = next(index for index in indexes if index["name"] == "ix_posts_location_cell_created_at")
    assert feed["column_names"] == ["location_cell", "created_at"]
