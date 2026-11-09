"""How far a feed reaches, in H3 cells: the radius in km becomes a whole number of rings."""

import h3
import pytest

from relay.contexts.posts.domain.cells import (
    CELL_RESOLUTION,
    MAX_RADIUS_KM,
    InvalidRadiusError,
    UnknownCellError,
)
from relay.contexts.posts.infrastructure.h3_neighbourhood import H3CellNeighbourhood, rings_for

# The two cells the location tests use: Vigo and A Coruña, about 170 km apart.
VIGO = "883920cd1bfffff"
A_CORUNA = "883925cf43fffff"

FEED = H3CellNeighbourhood()


def test_your_own_cell_is_always_in_your_feed() -> None:
    assert VIGO in FEED.visible_from(VIGO, 1)


def test_a_one_kilometre_radius_reaches_next_door_and_one_ring_past() -> None:
    """A res-8 ring is ~0.92 km across, so 1 km cannot be rounded down to a single ring."""
    visible = FEED.visible_from(VIGO, 1)
    assert set(h3.grid_disk(VIGO, 1)) < visible
    assert visible == set(h3.grid_disk(VIGO, 2))


def test_the_ten_kilometre_default_reaches_eleven_rings() -> None:
    # 11 rings of ~0.92 km cells is the first whole ring count that covers 10 km.
    assert rings_for(10) == 11
    assert len(FEED.visible_from(VIGO, 10)) == len(h3.grid_disk(VIGO, 11)) == 397


def test_a_radius_is_never_rounded_down_to_fewer_cells_than_it_asks_for() -> None:
    spacing = h3.average_hexagon_edge_length(CELL_RESOLUTION, unit="km") * 1.7320508
    for radius in (0.1, 1, 5, 10, 25):
        assert rings_for(radius) * spacing >= radius


def test_a_wider_radius_never_loses_a_cell_a_narrower_one_had() -> None:
    assert FEED.visible_from(VIGO, 2) <= FEED.visible_from(VIGO, 10) <= FEED.visible_from(VIGO, 25)


def test_a_town_on_the_other_side_of_the_region_is_not_in_this_feed() -> None:
    assert A_CORUNA not in FEED.visible_from(VIGO, MAX_RADIUS_KM)


@pytest.mark.parametrize("radius", [0, -5, MAX_RADIUS_KM + 0.1])
def test_a_radius_that_would_read_the_whole_country_is_refused(radius: float) -> None:
    with pytest.raises(InvalidRadiusError):
        FEED.visible_from(VIGO, radius)


@pytest.mark.parametrize("cell", ["", "not-a-cell", "8"])
def test_a_cell_that_is_not_a_cell_is_refused(cell: str) -> None:
    with pytest.raises(UnknownCellError):
        FEED.visible_from(cell, 10)


def test_a_cell_at_another_resolution_is_refused() -> None:
    """The feed filters on cells matching, so a res-7 cell would silently match nothing."""
    res_7 = h3.latlng_to_cell(42.23, -8.72, 7)
    with pytest.raises(UnknownCellError):
        FEED.visible_from(res_7, 10)
