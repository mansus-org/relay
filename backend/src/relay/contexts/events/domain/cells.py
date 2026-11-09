"""How far a list of what is on reaches from the cell a reader is standing in.

The events context asks H3 the same two questions the posts context does — how far a
ring goes, and what counts as a cell — and answers them the same way. It keeps its own
copy rather than importing posts' because a context owns its own ports: the day an
events list is allowed to reach further than a feed does, that is a change to make
here, and only here.
"""

from relay.shared.domain import DomainError

#: Events are filed at H3 resolution 8, the same cut the posts context serves its
#: feeds at and the location context cuts a postal code into. One cut, or an event
#: near you and a post near you would be two different neighbourhoods.
CELL_RESOLUTION = 8

#: How far out a reader looks for something to go to, by default. Ten kilometres is
#: the same neighbourhood they read their feed at.
DEFAULT_RADIUS_KM = 10.0

#: The ceiling on that. A k-ring grows quadratically and every cell in it goes into
#: the query: 10 km is 397 cells, 25 km is 2,437, and past that the query is the
#: bottleneck rather than the index. 25 km is also far enough that someone will
#: genuinely drive to what is in it.
MAX_RADIUS_KM = 25.0


class CellError(DomainError):
    """Base class for the ways a cell or a radius can be wrong."""


class UnknownCellError(CellError):
    """Not a cell Relay can look a neighbourhood up from."""


class InvalidRadiusError(CellError):
    """A radius no list of events is served at."""
