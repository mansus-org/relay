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
        # Written with a `Z`, not a `+00:00`: a `+` in a query string is a space by the
        # time it arrives, and a cursor is only any use if it survives the trip back.
        return self.value.astimezone(UTC).isoformat().replace("+00:00", "Z")

    @classmethod
    def parse(cls, raw: str) -> "Cursor":
        """Reads back what `__str__` wrote, and any other timestamp naming an instant.

        Raises InvalidCursorError if it is not a timestamp at all.
        """
        try:
            parsed = datetime.fromisoformat(raw.strip())
        except ValueError as error:
            raise InvalidCursorError("That is not a cursor this feed handed out.") from error
        # Compared in UTC, whatever zone it arrived in: that is the zone the feed is
        # stored in, and a cursor kept in another one would compare off by its offset.
        if parsed.tzinfo is None:
            # A cursor that names no zone means UTC: the feed only ever hands out UTC.
            parsed = parsed.replace(tzinfo=UTC)
        return cls(value=parsed.astimezone(UTC))


class FeedPage(ValueObject):
    """Newest posts first, and where to pick up the older ones."""

    posts: tuple[Post, ...]
    next_cursor: Cursor | None = None
