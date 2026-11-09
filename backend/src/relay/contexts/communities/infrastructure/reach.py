"""How far a community reaches from the cell it is anchored at."""

import h3

from relay.contexts.communities.domain.ports import CellReach
from relay.contexts.posts.infrastructure.h3_cells import rings_for, served_cell


class H3CommunityReach(CellReach):
    """Whether one cell is inside another cell's reach.

    The same geometry the locality feed draws as a disk around the reader, asked
    between two cells instead: `grid_distance` counts the rings between them and
    `rings_for` says how many a radius is worth, so a community's 5 km and a feed's 5 km
    are the same distance and cannot drift apart.
    """

    def covers(self, *, anchor: str, radius_km: float, cell: str) -> bool:
        centre = served_cell(anchor)
        standing = served_cell(cell)
        try:
            return h3.grid_distance(centre, standing) <= rings_for(radius_km)
        except h3.H3BaseException:
            # Two cells far enough apart land on different faces of the icosahedron, and
            # H3 has no grid path between those. Not a bug to raise over: no path means
            # nowhere near, which is the only answer the caller needed.
            return False
