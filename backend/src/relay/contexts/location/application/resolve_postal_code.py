"""Postal code to place to coarse cell: the only path from a typed code to a feed."""

from relay.contexts.location.domain.place import Locality
from relay.contexts.location.domain.ports import CellEncoder, PostalCodeDirectory
from relay.contexts.location.domain.postal_code import (
    PostalCode,
    PostalCodeOutsideAreaError,
    UnknownPostalCodeError,
    coverage_message,
)


class ResolvePostalCode:
    """Resolves a typed postal code into the locality and cell the client reads its feed from."""

    def __init__(self, directory: PostalCodeDirectory, cells: CellEncoder) -> None:
        self._directory = directory
        self._cells = cells

    async def execute(self, raw: str) -> Locality:
        """Raises the three postal errors; the api layer turns each into a status code."""
        code = PostalCode.parse(raw)
        if code.province is None:
            raise PostalCodeOutsideAreaError(coverage_message())

        place = await self._directory.find(code)
        if place is None:
            raise UnknownPostalCodeError(f"Relay has no {code} in its postal data yet.")

        return Locality(place=place, cell=self._cells.cell_of(place.latitude, place.longitude))
