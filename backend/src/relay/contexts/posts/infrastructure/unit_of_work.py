"""One session, one transaction, and the posts repository on it."""

from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.contexts.posts.application.unit_of_work import PostsUnitOfWork
from relay.contexts.posts.domain.ports import PostRepository
from relay.contexts.posts.infrastructure.repository import SqlAlchemyPostRepository
from relay.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyPostsUnitOfWork(SqlAlchemyUnitOfWork, PostsUnitOfWork):
    """The posts unit of work, built from the app's session factory."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(session_factory)

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.posts: PostRepository = SqlAlchemyPostRepository(self.session)
        return self
