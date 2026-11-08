"""Location domain: postal codes, the places they name, and the cells their feeds use."""

from relay.contexts.location.domain.place import Cell, Locality, PostalPlace
from relay.contexts.location.domain.ports import CellEncoder, PostalCodeDirectory
from relay.contexts.location.domain.postal_code import (
    InvalidPostalCodeError,
    PostalCode,
    PostalCodeError,
    PostalCodeOutsideAreaError,
    PostalDataUnavailableError,
    Province,
    UnknownPostalCodeError,
    coverage_message,
)

__all__ = [
    "Cell",
    "CellEncoder",
    "InvalidPostalCodeError",
    "Locality",
    "PostalCode",
    "PostalCodeDirectory",
    "PostalCodeError",
    "PostalCodeOutsideAreaError",
    "PostalDataUnavailableError",
    "PostalPlace",
    "Province",
    "UnknownPostalCodeError",
    "coverage_message",
]
