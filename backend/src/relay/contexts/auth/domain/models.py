"""An entity whose identity is a row number the database hands out.

`shared.domain.Entity` assumes a uuid the object makes for itself. The auth tables
are INTEGER PRIMARY KEY, so the id only exists after an insert; this base makes
that legal and stops two not-yet-saved rows from comparing equal.
"""

from typing import Any

from relay.shared.domain import Entity


class RelationalEntity(Entity):
    """An Entity identified by an autoincrement integer, None until it has been inserted."""

    id: int | None = None  # ty: ignore - the row number replaces the uuid, on purpose

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, type(self)):
            return False
        if self.id is None or other.id is None:
            return self is other
        return self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))

    def require_id(self) -> int:
        """The row number. Raises when the entity has not been inserted yet."""
        if self.id is None:
            raise RuntimeError(f"{type(self).__name__} has no id until it has been saved")
        return self.id
