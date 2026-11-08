"""The H3 cut must match the client's, or a typed code and a GPS fix land in different grids."""

import h3

from relay.contexts.location.infrastructure.h3_cells import RESOLUTION, H3CellEncoder


def test_cuts_a_resolution_8_cell_like_the_client_does() -> None:
    # A Coruña, the same coordinate the mobile h3 tests use.
    cell = H3CellEncoder().cell_of(43.3718, -8.3958)
    assert str(cell) == h3.latlng_to_cell(43.3718, -8.3958, 8)
    assert h3.get_resolution(str(cell)) == RESOLUTION == 8


def test_nearby_points_share_one_cell() -> None:
    encoder = H3CellEncoder()
    assert encoder.cell_of(43.3718, -8.3958) == encoder.cell_of(43.3724, -8.3961)
