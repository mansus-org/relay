import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from relay.container import Container
from relay.contexts.communities.api import communities
from relay.contexts.location.api import location
from relay.contexts.posts.api import posts
from relay.shared.api import health
from relay.shared.api.web import web_router
from relay.shared.config import Settings
from relay.shared.infrastructure.database import create_engine, create_session_factory
from relay.shared.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings) -> FastAPI:
    """Composition root: the only place that builds Settings-dependent objects."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        configure_logging(settings.log_level)
        engine = create_engine(settings.database_url)
        app.state.container = Container(settings, create_session_factory(engine))
        logger.info("startup", extra={"version": settings.version})
        try:
            yield
        finally:
            await engine.dispose()
            logger.info("shutdown")

    app = FastAPI(title="Relay", version=settings.version, lifespan=lifespan)
    app.include_router(health.router, prefix="/api")
    app.include_router(location.router, prefix="/api")
    app.include_router(posts.router, prefix="/api")
    app.include_router(communities.router, prefix="/api")
    app.include_router(health.router)  # plain /health for container probes
    if settings.web_dist_dir is not None:
        app.include_router(web_router(settings.web_dist_dir))  # last: it matches every other path
    return app


app = create_app(Settings())
