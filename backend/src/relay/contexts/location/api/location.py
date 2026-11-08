"""HTTP edge of the location context."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from relay.container import Container
from relay.contexts.location.application.resolve_postal_code import ResolvePostalCode
from relay.contexts.location.domain.place import Locality
from relay.contexts.location.domain.postal_code import (
    InvalidPostalCodeError,
    PostalCodeOutsideAreaError,
    PostalDataUnavailableError,
    UnknownPostalCodeError,
    coverage_message,
)
from relay.shared.api.dependencies import get_container

router = APIRouter(prefix="/location", tags=["location"])

ATTRIBUTION = "Postal data: GeoNames (https://www.geonames.org), CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)."


class AreaResponse(BaseModel):
    """What a postal code resolves to: a name to show, and the cell to read the feed from."""

    postal_code: str
    place_name: str
    cell: str

    @classmethod
    def from_domain(cls, locality: Locality) -> "AreaResponse":
        return cls(
            postal_code=str(locality.place.postal_code),
            place_name=locality.place.label,
            cell=str(locality.cell),
        )


def get_postal_code_resolver(
    container: Annotated[Container, Depends(get_container)],
) -> ResolvePostalCode:
    return container.get_resolve_postal_code()


@router.get(
    "/postal-code/{postal_code}",
    response_model=AreaResponse,
    summary="Resolve a postal code into a locality and its feed cell",
    description=f"{ATTRIBUTION} {coverage_message()}",
    responses={
        400: {"description": "Not five digits"},
        404: {"description": "Valid code, but outside the covered area or not in the shipped data"},
        503: {"description": "The shipped postal data could not be read"},
    },
)
async def resolve_postal_code(
    postal_code: str,
    resolver: Annotated[ResolvePostalCode, Depends(get_postal_code_resolver)],
) -> AreaResponse:
    try:
        locality = await resolver.execute(postal_code)
    except InvalidPostalCodeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except (PostalCodeOutsideAreaError, UnknownPostalCodeError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PostalDataUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return AreaResponse.from_domain(locality)
