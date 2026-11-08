"""The postal codes Relay ships: a GeoNames extract read once and held in memory."""

import json
from pathlib import Path
from typing import Any

from relay.contexts.location.domain.place import PostalPlace
from relay.contexts.location.domain.ports import PostalCodeDirectory
from relay.contexts.location.domain.postal_code import PostalCode, PostalDataUnavailableError
from relay.shared.domain import DomainError

#: Built by scripts/build_postal_codes.py; see that script for provenance and how to refresh it.
DEFAULT_DATASET = Path(__file__).parent / "data" / "postal-codes-galicia.json"


def load_postal_dataset(path: Path) -> dict[PostalCode, PostalPlace]:
    """Reads the shipped dataset into a lookup. Raises PostalDataUnavailableError if it cannot."""

    def read() -> dict[PostalCode, PostalPlace]:
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        by_code: dict[PostalCode, PostalPlace] = {}
        for entry in payload["codes"]:
            code = PostalCode.parse(entry["code"])
            by_code[code] = PostalPlace(
                postal_code=code,
                name=entry["name"],
                province=entry["province"],
                municipality=entry["municipality"],
                latitude=entry["lat"],
                longitude=entry["lng"],
            )
        return by_code

    try:
        return read()
    except (OSError, KeyError, TypeError, ValueError, DomainError) as error:
        raise PostalDataUnavailableError(
            f"Relay's postal data could not be read ({path.name})."
        ) from error


class DatasetPostalCodeDirectory(PostalCodeDirectory):
    """Postal codes from the shipped dataset, read on first lookup and then kept."""

    def __init__(self, path: Path = DEFAULT_DATASET) -> None:
        self._path = path
        self._by_code: dict[PostalCode, PostalPlace] | None = None

    async def find(self, code: PostalCode) -> PostalPlace | None:
        if self._by_code is None:
            # One ~250 KB read per process; not worth a thread or a startup hook.
            self._by_code = load_postal_dataset(self._path)
        return self._by_code.get(code)
