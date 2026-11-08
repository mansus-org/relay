"""The shipped GeoNames extract: what it promises, and what happens when it cannot be read."""

import json
from pathlib import Path

import pytest

from relay.contexts.location.domain import PostalCode, PostalDataUnavailableError, Province
from relay.contexts.location.infrastructure.postal_directory import (
    DEFAULT_DATASET,
    DatasetPostalCodeDirectory,
    load_postal_dataset,
)

MIN_CODES = 300


def write(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "codes.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


async def test_reads_a_dataset_file_into_a_lookup(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        {
            "codes": [
                {
                    "code": "36201",
                    "name": "Vigo",
                    "province": "Pontevedra",
                    "municipality": "Vigo",
                    "lat": 42.237,
                    "lng": -8.722,
                }
            ]
        },
    )
    place = await DatasetPostalCodeDirectory(path).find(PostalCode(value="36201"))
    assert place is not None
    assert place.label == "Vigo"
    assert await DatasetPostalCodeDirectory(path).find(PostalCode(value="15001")) is None


@pytest.mark.parametrize(
    "broken", ["not json at all", '{"codes": [{"code": "15001"}]}', "{}", "[]"]
)
async def test_an_unreadable_dataset_raises_instead_of_resolving_nothing(
    tmp_path: Path, broken: str
) -> None:
    path = tmp_path / "codes.json"
    path.write_text(broken, encoding="utf-8")
    with pytest.raises(PostalDataUnavailableError):
        await DatasetPostalCodeDirectory(path).find(PostalCode(value="15001"))


async def test_a_missing_file_is_reported_as_an_unavailable_dataset(tmp_path: Path) -> None:
    with pytest.raises(PostalDataUnavailableError):
        await DatasetPostalCodeDirectory(tmp_path / "nope.json").find(PostalCode(value="15001"))


@pytest.fixture(scope="module")
def shipped() -> dict:
    return json.loads(DEFAULT_DATASET.read_text(encoding="utf-8"))


def test_the_shipped_dataset_covers_galicia_and_nothing_else(shipped: dict) -> None:
    codes = shipped["codes"]
    assert len(codes) >= MIN_CODES
    assert {entry["province"] for entry in codes} == {
        Province.A_CORUNA,
        Province.LUGO,
        Province.OURENSE,
        Province.PONTEVEDRA,
    }
    assert all(entry["code"].startswith(tuple(shipped["prefixes"])) for entry in codes)
    assert all(len(entry["code"]) == 5 and entry["name"] for entry in codes)
    assert all(-90 <= entry["lat"] <= 90 and -180 <= entry["lng"] <= 180 for entry in codes)


def test_the_shipped_dataset_carries_its_licence(shipped: dict) -> None:
    assert "GeoNames" in shipped["attribution"]
    assert "CC BY" in shipped["attribution"]
    assert "geonames.org" in shipped["source"]
    assert shipped["retrieved"]


def test_the_shipped_dataset_loads_whole_and_fits_in_the_image() -> None:
    assert DEFAULT_DATASET.stat().st_size < 600_000
    loaded = load_postal_dataset(DEFAULT_DATASET)
    assert len(loaded) == len(json.loads(DEFAULT_DATASET.read_text())["codes"])


@pytest.mark.parametrize(
    ("code", "label"),
    [("15001", "A Coruña"), ("27001", "Lugo"), ("32003", "Ourense"), ("36201", "Vigo")],
)
async def test_the_shipped_dataset_answers_for_a_capital_of_each_province(
    code: str, label: str
) -> None:
    place = await DatasetPostalCodeDirectory().find(PostalCode(value=code))
    assert place is not None
    assert place.label == label
