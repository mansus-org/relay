"""The postal-code endpoint: a code in, a cell out, and a status per way a code can be wrong."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from relay.contexts.location.infrastructure.postal_directory import DatasetPostalCodeDirectory
from relay.main import create_app
from relay.shared.config import Settings


@pytest.mark.parametrize(
    ("code", "place", "cell"),
    [
        ("15001", "A Coruña", "883925cf43fffff"),
        ("27001", "Lugo", "88392560b9fffff"),
        ("32003", "Ourense", "88392031a9fffff"),
        ("36201", "Vigo", "883920cd1bfffff"),
    ],
)
async def test_a_galician_code_returns_the_place_and_the_cell_to_read_from(
    client: AsyncClient, code: str, place: str, cell: str
) -> None:
    response = await client.get(f"/api/location/postal-code/{code}")
    assert response.status_code == 200
    assert response.json() == {"postal_code": code, "place_name": place, "cell": cell}


async def test_a_code_with_spaces_still_resolves(client: AsyncClient) -> None:
    assert (await client.get("/api/location/postal-code/%2036201")).status_code == 200


@pytest.mark.parametrize("code", ["1234", "150011", "1500A"])
async def test_a_malformed_code_is_a_400_with_the_rule(client: AsyncClient, code: str) -> None:
    response = await client.get(f"/api/location/postal-code/{code}")
    assert response.status_code == 400
    assert "5 digits" in response.json()["detail"]


@pytest.mark.parametrize("code", ["28001", "08001"])
async def test_a_code_outside_galicia_is_a_404_naming_the_covered_prefixes(
    client: AsyncClient, code: str
) -> None:
    response = await client.get(f"/api/location/postal-code/{code}")
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "Galicia" in detail
    assert all(prefix in detail for prefix in ("15", "27", "32", "36"))


async def test_a_galician_code_outside_the_shipped_data_is_a_404(client: AsyncClient) -> None:
    response = await client.get("/api/location/postal-code/32999")
    assert response.status_code == 404
    assert "32999" in response.json()["detail"]


async def test_an_unreadable_dataset_is_a_503_not_a_wrong_cell(test_settings: Settings) -> None:
    app = create_app(test_settings)
    async with app.router.lifespan_context(app):
        missing = DatasetPostalCodeDirectory(Path("/nonexistent/codes.json"))
        app.state.container.postal_codes = missing
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            response = await http.get("/api/location/postal-code/15001")
    assert response.status_code == 503
    assert "postal data" in response.json()["detail"]


async def test_the_endpoint_publishes_its_data_licence(client: AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()
    description = schema["paths"]["/api/location/postal-code/{postal_code}"]["get"]["description"]
    assert "GeoNames" in description
    assert "CC BY" in description
