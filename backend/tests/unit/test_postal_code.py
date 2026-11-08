"""The postal-code rules: five digits, Galicia, and a name short enough to put in a header."""

import pytest

from relay.contexts.location.domain import (
    Cell,
    InvalidPostalCodeError,
    PostalCode,
    PostalPlace,
    Province,
    coverage_message,
)


def test_parses_a_five_digit_code_and_trims_spaces() -> None:
    assert PostalCode.parse("15001").value == "15001"
    assert str(PostalCode.parse(" 36201 ")) == "36201"


@pytest.mark.parametrize("raw", ["", "   ", "1234", "150011", "1500A", "28-1", "one"])
def test_rejects_anything_that_is_not_five_digits(raw: str) -> None:
    with pytest.raises(InvalidPostalCodeError):
        PostalCode.parse(raw)


@pytest.mark.parametrize(
    ("code", "province"),
    [
        ("15001", Province.A_CORUNA),
        ("27001", Province.LUGO),
        ("32003", Province.OURENSE),
        ("36201", Province.PONTEVEDRA),
    ],
)
def test_maps_the_galician_prefixes_to_provinces(code: str, province: str) -> None:
    assert PostalCode.parse(code).province == province


@pytest.mark.parametrize("code", ["28001", "08001", "51001"])
def test_everything_else_is_outside_the_covered_area(code: str) -> None:
    assert PostalCode.parse(code).province is None


def test_the_out_of_area_message_names_the_covered_prefixes() -> None:
    message = coverage_message()
    assert "Galicia" in message
    assert all(prefix in message for prefix in Province.prefixes())


def test_a_cell_prints_as_its_value() -> None:
    assert str(Cell(value="883925cf43fffff")) == "883925cf43fffff"


def place(**overrides: object) -> PostalPlace:
    fields: dict[str, object] = {
        "postal_code": PostalCode(value="36201"),
        "name": "Vigo",
        "province": "Pontevedra",
        "municipality": "Vigo",
        "latitude": 42.237,
        "longitude": -8.722,
    }
    fields.update(overrides)
    return PostalPlace(**fields)  # type: ignore[arg-type]


def test_a_place_shows_the_municipality_only_when_it_adds_something() -> None:
    assert place().label == "Vigo"
    hamlet = place(name="Bertoa (Santa Maria)", municipality="Carballo")
    assert hamlet.label == "Bertoa (Santa Maria), Carballo"
