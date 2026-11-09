import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from relay.main import create_app
from relay.shared.config import Settings
from relay.shared.infrastructure.database import create_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    """TEST_DATABASE_URL (Postgres in CI) when set, else a throwaway SQLite file."""
    return os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def test_settings(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
        version="test",
        # The suite signs tokens with the development key, which a deployment has to
        # opt into out loud. Here it is on purpose: nothing outside this process reads it.
        allow_insecure_secret_key=True,
    )


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture
async def migrated_engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    """An engine on a database with all migrations applied (never create_all)."""
    # env.py drives its own event loop, so run it off this one.
    config = alembic_config(database_url)
    await asyncio.to_thread(command.upgrade, config, "head")
    engine = create_engine(database_url)
    try:
        yield engine
    finally:
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, config, "base")


@pytest.fixture
async def client(test_settings: Settings) -> AsyncIterator[AsyncClient]:
    app = create_app(test_settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            yield http
