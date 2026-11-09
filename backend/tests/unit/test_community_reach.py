"""How far a community reaches, which has to be the same distance the locality feed draws.

The join rule is the whole of RELY-89's locality scope, and it is all arithmetic: get
the ring count wrong and either a neighbour two streets away is told they live too far
out, or someone from the next town joins a street's community.
"""

import h3
import pytest

from relay.contexts.communities.infrastructure.reach import H3CommunityReach
from relay.contexts.posts.domain.cells import MAX_RADIUS_KM, UnknownCellError
from relay.contexts.posts.infrastructure.h3_cells import H3CellNeighbourhood, rings_for

#: Vigo, the cell the posts tests use.
VIGO = "883920cd1bfffff"
#: Pontevedra: 26 rings down the coast, inside what a 50 km community reaches and out of
#: the question for a 5 km one.
PONTEVEDRA = "883920c403fffff"
#: A cell on the far side of New Zealand, on another face of the icosahedron than Vigo is.
FAR_AWAY = "88bb2942d3fffff"

reach = H3CommunityReach()
feed = H3CellNeighbourhood()


def test_a_community_covers_the_cell_it_is_anchored_at() -> None:
    assert reach.covers(anchor=VIGO, radius_km=1, cell=VIGO)


def test_the_cells_a_community_reaches_are_the_ones_the_feed_would_draw() -> None:
    """The join rule and the feed rule are the same rule.

    Every cell inside the disk the locality feed draws around Vigo is inside a
    community anchored at Vigo for the same radius, and the ring beyond it is not.
    """
    near = feed.visible_from(VIGO, 5)
    one_ring_more = set(h3.grid_disk(VIGO, rings_for(5) + 1)) - near

    assert all(reach.covers(anchor=VIGO, radius_km=5, cell=cell) for cell in near)
    assert one_ring_more
    assert not any(reach.covers(anchor=VIGO, radius_km=5, cell=cell) for cell in one_ring_more)


def test_a_five_kilometre_community_does_not_reach_the_next_town() -> None:
    assert not reach.covers(anchor=VIGO, radius_km=5, cell=PONTEVEDRA)


def test_a_fifty_kilometre_community_does() -> None:
    assert reach.covers(anchor=VIGO, radius_km=MAX_RADIUS_KM, cell=PONTEVEDRA)


def test_the_other_side_of_the_world_is_not_near() -> None:
    """H3 cannot count rings between cells on different faces of the icosahedron. That
    is not an error to raise over: nowhere near is the only answer the caller wanted."""
    assert not reach.covers(anchor=VIGO, radius_km=MAX_RADIUS_KM, cell=FAR_AWAY)


def test_a_cell_at_another_resolution_is_refused() -> None:
    """A resolution-9 cell is not "far away", it is not a cell Relay can use, and saying
    so beats a join that would have been refused for the wrong reason."""
    coarser = h3.cell_to_parent(VIGO, 7)

    with pytest.raises(UnknownCellError):
        reach.covers(anchor=VIGO, radius_km=5, cell=coarser)


def test_a_cell_that_is_not_a_cell_is_refused() -> None:
    with pytest.raises(UnknownCellError):
        reach.covers(anchor="not a cell", radius_km=5, cell=VIGO)


def test_the_reach_does_not_care_who_written_the_cell_down() -> None:
    """Cells come in from a phone and from a query string, and both are allowed to be
    untidy about case and spaces."""
    assert reach.covers(anchor=f"  {VIGO.upper()} ", radius_km=5, cell=f" {VIGO} ")
