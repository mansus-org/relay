"""A page of a locality feed, and the cursor that walks one backwards in time."""

from datetime import UTC, datetime

from relay.contexts.posts.domain.post import Post
from relay.shared.domain import DomainError, ValueObject


class InvalidCursorError(DomainError):
    """Not a cursor this feed handed out."""


class Cursor(ValueObject):
    """Where a page ended: the `created_at` of its last post. The next page starts before it.

    Posts are ordered by `created_at` alone, so two posts sharing a timestamp means
    the earlier of the two is skipped rather than repeated. Feed timestamps come from
    one clock and are distinct to the microsecond; a cursor that also carried the id
    is the fix if that ever stops being true.
    """

    value: datetime

    def __str__(self) -> str:
        return self.value.astimezone(UTC).isoformat()

    @classmethod
    def parse(cls, raw: str) -> "Cursor":
        """Reads back what `__str__` wrote. Raises InvalidCursorError if it is not that."""
        try:
            parsed = datetime.fromisoformat(raw.strip())
        except ValueError as error:
            raise InvalidCursorError("That is not a cursor this feed handed out.") from error
        # A cursor that names no zone means UTC: the feed only ever hands out UTC.
        return cls(value=parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed)


class FeedPage(ValueObject):
    """Newest posts first, and where to pick up the older ones."""

    posts: tuple[Post, ...]
    next_cursor: Cursor | None = None
