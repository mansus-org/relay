"""H3 cells: the same cut the client makes, so a typed code and a GPS fix land in one grid."""

import h3

from relay.contexts.location.domain.place import Cell
from relay.contexts.location.domain.ports import CellEncoder

#: Must stay equal to H3_RESOLUTION in mobile/src/infrastructure/location/h3-cell-encoder.ts.
RESOLUTION = 8


class H3CellEncoder(CellEncoder):
    """Cuts a point into the resolution-8 cell Relay serves feeds from."""

    def cell_of(self, latitude: float, longitude: float) -> Cell:
        return Cell(value=h3.latlng_to_cell(latitude, longitude, RESOLUTION))
