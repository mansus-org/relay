"""H3, in the two ways the events context asks about it: how far a list reaches, and
what counts as a cell."""

import math

import h3

from relay.contexts.events.domain.cells import (
    CELL_RESOLUTION,
    MAX_RADIUS_KM,
    InvalidRadiusError,
    UnknownCellError,
)
from relay.contexts.events.domain.ports import CellNeighbourhood, CellStandard


def rings_for(radius_km: float) -> int:
    """How many k-rings it takes to reach `radius_km` out from a cell.

    Adjacent cell centres sit about sqrt(3) x edge length apart, so the ring count is
    the radius over that spacing, rounded up: someone asking for 10 km is never handed
    9. Rounding up is also what makes the ring cover the circle at its corners.
    """
    spacing_km = math.sqrt(3) * h3.average_hexagon_edge_length(CELL_RESOLUTION, unit="km")
    return math.ceil(radius_km / spacing_km)


def served_cell(cell: str) -> str:
    """`cell` in the one form Relay stores and queries cells in: trimmed, lowercase.

    Raises UnknownCellError for anything no list could be read from and no event could
    be filed under: not a cell at all, or a cell at another resolution. Both are the
    writer's and the reader's mistake to hear about now, not a row that quietly
    matches nothing later.
    """
    named = cell.strip().lower()
    if not _is_a_cell(named):
        raise UnknownCellError(f"{cell!r} is not an H3 cell.")
    resolution = h3.get_resolution(named)
    if resolution != CELL_RESOLUTION:
        raise UnknownCellError(
            f"Relay works at resolution {CELL_RESOLUTION}, not resolution {resolution}."
        )
    return named


def _is_a_cell(candidate: str) -> bool:
    try:
        return h3.is_valid_cell(candidate)
    except (OverflowError, ValueError):
        # H3 will not even test a string too long to be one of its indexes.
        return False


class EventsCellNeighbourhood(CellNeighbourhood):
    """The k-ring around the reader's cell, which is what the list query filters on."""

    def visible_from(self, cell: str, radius_km: float) -> set[str]:
        named = served_cell(cell)
        if not 0 < radius_km <= MAX_RADIUS_KM:
            raise InvalidRadiusError(f"Radius must be between 0 and {MAX_RADIUS_KM} km.")
        return set(h3.grid_disk(named, rings_for(radius_km)))


class EventsCellStandard(CellStandard):
    """What H3 says a cell is, so an event is filed where a list will look for it."""

    def normalise(self, cell: str) -> str:
        return served_cell(cell)
