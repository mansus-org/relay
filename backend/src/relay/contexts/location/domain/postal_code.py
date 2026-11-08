"""Postal codes, and the area Relay is willing to serve. Pure: no framework imports."""

import re
from typing import ClassVar

from relay.shared.domain import DomainError, ValueObject

_FIVE_DIGITS = re.compile(r"^\d{5}$")


class PostalCodeError(DomainError):
    """Base for every rejection the postal lookup raises."""


class InvalidPostalCodeError(PostalCodeError):
    """Not a five-digit Spanish postal code."""


class PostalCodeOutsideAreaError(PostalCodeError):
    """Well formed, but outside the area Relay covers."""


class UnknownPostalCodeError(PostalCodeError):
    """Inside the covered area, but the shipped data has no entry for it."""


class PostalDataUnavailableError(PostalCodeError):
    """The shipped postal data could not be read, so nothing can be resolved."""


class Province:
    """The Galician provinces, each named for the postal-code prefix that covers it."""

    A_CORUNA = "A Coruña"
    LUGO = "Lugo"
    OURENSE = "Ourense"
    PONTEVEDRA = "Pontevedra"

    _BY_PREFIX: ClassVar[dict[str, str]] = {
        "15": A_CORUNA,
        "27": LUGO,
        "32": OURENSE,
        "36": PONTEVEDRA,
    }

    @classmethod
    def prefixes(cls) -> tuple[str, ...]:
        """The two-digit prefixes Relay covers, in order."""
        return tuple(cls._BY_PREFIX)

    @classmethod
    def covering(cls, code: "PostalCode") -> str | None:
        """The province a code falls in, or None when it is outside Galicia."""
        return cls._BY_PREFIX.get(code.value[:2])


def coverage_message() -> str:
    """What to tell someone whose code is outside the covered area."""
    return (
        f"Relay is only in Galicia for now: postal codes starting {', '.join(Province.prefixes())}."
    )


class PostalCode(ValueObject):
    """A Spanish postal code: five digits. Whether Relay covers it is a separate question."""

    value: str

    @classmethod
    def parse(cls, raw: str) -> "PostalCode":
        """Trim and validate, raising instead of returning None so the caller gets a message."""
        value = raw.strip()
        if not _FIVE_DIGITS.match(value):
            raise InvalidPostalCodeError(f"Postal codes are 5 digits, '{value}' is not.")
        return cls(value=value)

    @property
    def province(self) -> str | None:
        return Province.covering(self)

    def __str__(self) -> str:
        return self.value
