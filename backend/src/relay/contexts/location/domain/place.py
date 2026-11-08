"""The place a postal code names, and the coarse cell its feed is served from."""

from relay.contexts.location.domain.postal_code import PostalCode
from relay.shared.domain import ValueObject


class Cell(ValueObject):
    """A coarse H3 area. Feeds are keyed by this string, never by raw coordinates."""

    value: str

    def __str__(self) -> str:
        return self.value


class PostalPlace(ValueObject):
    """What a postal code names: a label to show and a point to cut the cell from."""

    postal_code: PostalCode
    name: str
    province: str
    municipality: str
    latitude: float
    longitude: float

    @property
    def label(self) -> str:
        """Shortest name that still places it: 'Vigo', or 'Quinta (Santa Eulalia), Becerreá'."""
        return self.name if self.name == self.municipality else f"{self.name}, {self.municipality}"


class Locality(ValueObject):
    """A resolved postal area: the place, and the cell Relay serves its feed from."""

    place: PostalPlace
    cell: Cell
