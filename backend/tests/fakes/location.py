from relay.contexts.location.domain.place import Cell, PostalPlace
from relay.contexts.location.domain.ports import CellEncoder, PostalCodeDirectory
from relay.contexts.location.domain.postal_code import PostalCode


class StubCellEncoder(CellEncoder):
    """Cells without H3, so a test can name the cell it expects."""

    def cell_of(self, latitude: float, longitude: float) -> Cell:
        return Cell(value=f"cell@{latitude},{longitude}")


class StubPostalCodeDirectory(PostalCodeDirectory):
    """A postal directory someone hands a dict, for use-case tests."""

    def __init__(self, places: dict[str, PostalPlace] | None = None) -> None:
        given = places or {}
        self._places: dict[PostalCode, PostalPlace] = {
            PostalCode(value=code): place for code, place in given.items()
        }

    async def find(self, code: PostalCode) -> PostalPlace | None:
        return self._places.get(code)
