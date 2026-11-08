"""Ports the location context needs; infrastructure supplies the implementations."""

from abc import ABC, abstractmethod

from relay.contexts.location.domain.place import Cell, PostalPlace
from relay.contexts.location.domain.postal_code import PostalCode


class PostalCodeDirectory(ABC):
    """Lookup of the postal codes Relay knows. A shipped dataset, not a database table."""

    @abstractmethod
    async def find(self, code: PostalCode) -> PostalPlace | None: ...


class CellEncoder(ABC):
    """Cuts a point into the coarse cell a locality feed is served from."""

    @abstractmethod
    def cell_of(self, latitude: float, longitude: float) -> Cell: ...
