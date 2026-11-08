"""Resolving a typed code: the three ways it fails, and the cell it produces when it works."""

import pytest

from relay.contexts.location.application import ResolvePostalCode
from relay.contexts.location.domain import (
    InvalidPostalCodeError,
    PostalCode,
    PostalCodeOutsideAreaError,
    PostalPlace,
    UnknownPostalCodeError,
)
from tests.fakes.location import StubCellEncoder, StubPostalCodeDirectory

VIGO = PostalPlace(
    postal_code=PostalCode(value="36201"),
    name="Vigo",
    province="Pontevedra",
    municipality="Vigo",
    latitude=42.237,
    longitude=-8.722,
)


def service(places: dict[str, PostalPlace] | None = None) -> ResolvePostalCode:
    directory = StubPostalCodeDirectory(places or {"36201": VIGO})
    return ResolvePostalCode(directory=directory, cells=StubCellEncoder())


async def test_a_known_code_gives_the_place_and_a_cell_cut_from_its_point() -> None:
    locality = await service().execute("36201")
    assert locality.place == VIGO
    assert str(locality.cell) == "cell@42.237,-8.722"


async def test_a_code_is_looked_up_trimmed() -> None:
    assert (await service().execute(" 36201 ")).place == VIGO


async def test_a_malformed_code_is_rejected_before_any_lookup() -> None:
    with pytest.raises(InvalidPostalCodeError):
        await service().execute("Vigo")


async def test_a_code_outside_galicia_says_so_with_the_covered_prefixes() -> None:
    with pytest.raises(PostalCodeOutsideAreaError) as caught:
        await service().execute("28001")
    assert "Galicia" in str(caught.value)


async def test_a_galician_code_the_data_does_not_have_is_not_silently_a_cell() -> None:
    with pytest.raises(UnknownPostalCodeError):
        await service().execute("32999")
