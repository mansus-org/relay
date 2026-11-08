import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from relay.container import Container
from relay.contexts.auth.api import auth
from relay.contexts.location.api import location
from relay.shared.api import health
from relay.shared.api.web import web_router
from relay.shared.config import DEV_SECRET_KEY, Settings
from relay.shared.infrastructure.database import create_engine, create_session_factory
from relay.shared.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings) -> FastAPI:
    """Composition root: the only place that builds Settings-dependent objects."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        configure_logging(settings.log_level)
        if settings.secret_key == DEV_SECRET_KEY:
            logger.warning(
                "SECRET_KEY is still the development default: set one before anyone connects."
            )
        engine = create_engine(settings.database_url)
        app.state.container = Container(settings, create_session_factory(engine))
        await _seed_first_admin(app.state.container)
        logger.info("startup", extra={"version": settings.version})
        try:
            yield
        finally:
            await engine.dispose()
            logger.info("shutdown")

    app = FastAPI(title="Relay", version=settings.version, lifespan=lifespan)
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(location.router, prefix="/api")
    app.include_router(health.router)  # plain /health for container probes
    if settings.web_dist_dir is not None:
        app.include_router(web_router(settings.web_dist_dir))  # last: it matches every other path
    return app


async def _seed_first_admin(container: Container) -> None:
    """The first account, if the operator asked for one and the database has nobody yet.

    Opt-in through ADMIN_USERNAME and ADMIN_PASSWORD. With them unset a fresh database
    stays invite-only, exactly as it was, and nothing here touches the tables.
    """
    settings = container.settings
    if not (settings.admin_username and settings.admin_password):
        return
    user = await container.get_ensure_first_admin().execute(
        username=settings.admin_username, password=settings.admin_password
    )
    if user is not None:
        logger.warning("first account created", extra={"username": str(user.username)})


app = create_app(Settings())
