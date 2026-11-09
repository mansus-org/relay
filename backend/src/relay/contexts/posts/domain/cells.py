"""How far a locality feed reaches from the cell a reader is standing in."""

from relay.shared.domain import DomainError

#: Feeds are served at H3 resolution 8: the same cut the client sends and the
#: location context cuts a postal code into.
CELL_RESOLUTION = 8

#: How far out a reader looks by default. Matches FEED_RADIUS_KM in
#: mobile/src/domain/post.ts, the screen that reads the feed.
DEFAULT_RADIUS_KM = 10.0

#: The ceiling on that. A k-ring grows quadratically and every cell in it goes into
#: the feed query: 10 km is 397 cells, 25 km is 2,437, and past that the query is
#: the bottleneck rather than the index.
MAX_RADIUS_KM = 25.0


class CellError(DomainError):
    """Base class for the ways a cell or a radius can be wrong."""


class UnknownCellError(CellError):
    """Not a cell Relay can look a neighbourhood up from."""


class InvalidRadiusError(CellError):
    """A radius no feed is served at."""
