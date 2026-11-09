"""The neighbourhood, in H3 cells: how far out from the reader's cell a feed reaches."""

import math

import h3

from relay.contexts.posts.domain.cells import (
    CELL_RESOLUTION,
    MAX_RADIUS_KM,
    InvalidRadiusError,
    UnknownCellError,
)
from relay.contexts.posts.domain.ports import CellNeighbourhood


def rings_for(radius_km: float) -> int:
    """How many k-rings it takes to reach `radius_km` out from a cell.

    Adjacent cell centres sit about sqrt(3) x edge length apart, so the ring count is
    the radius over that spacing, rounded up: someone asking for 10 km is never handed
    9. Rounding up is also what makes the ring cover the circle at its corners.
    """
    spacing_km = math.sqrt(3) * h3.average_hexagon_edge_length(CELL_RESOLUTION, unit="km")
    return math.ceil(radius_km / spacing_km)


class H3CellNeighbourhood(CellNeighbourhood):
    """The k-ring around the reader's cell, which is what the feed query filters on."""

    def visible_from(self, cell: str, radius_km: float) -> set[str]:
        if not h3.is_valid_cell(cell):
            raise UnknownCellError(f"{cell!r} is not an H3 cell.")
        resolution = h3.get_resolution(cell)
        if resolution != CELL_RESOLUTION:
            raise UnknownCellError(
                f"Feeds are served at resolution {CELL_RESOLUTION}, not {resolution}."
            )
        if not 0 < radius_km <= MAX_RADIUS_KM:
            raise InvalidRadiusError(f"Radius must be between 0 and {MAX_RADIUS_KM} km.")
        return set(h3.grid_disk(cell, rings_for(radius_km)))
