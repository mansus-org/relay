from abc import ABC, abstractmethod

from relay.shared.domain.models import Entity


class Repository[E: Entity, ID](ABC):
    """Collection-like access to one aggregate root. Each context's repository subclasses it."""

    @abstractmethod
    async def get(self, id: ID) -> E | None: ...

    @abstractmethod
    async def add(self, entity: E) -> None:
        """Insert or update the aggregate. Afterwards it has the id the database gave it."""
