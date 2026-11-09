import asyncio

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# Every context's tables hang off Base.metadata, and importing them is how autogenerate
# gets to see them. A new context with a table adds a line here.
from relay.contexts.communities.infrastructure import models as community_models  # noqa: F401
from relay.contexts.posts.infrastructure import models  # noqa: F401
from relay.shared.config import Settings
from relay.shared.infrastructure.database import Base

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    """An explicit sqlalchemy.url (tests set one) wins over DATABASE_URL."""
    return config.get_main_option("sqlalchemy.url") or Settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_database_url())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
