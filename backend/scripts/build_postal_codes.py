#!/usr/bin/env python3
"""Build the trimmed postal-code dataset the location lookup reads.

Source: the GeoNames postal-code dump for Spain, https://download.geonames.org/export/zip/ES.zip
(GeoNames, CC BY 4.0, https://creativecommons.org/licenses/by/4.0/). We keep the four Galician
province prefixes and one row per postal code, so the lookup is offline and no geocoding call
happens at runtime.

    uv run python scripts/build_postal_codes.py            # downloads the dump
    uv run python scripts/build_postal_codes.py --source /tmp/geonames/ES.txt
"""

from __future__ import annotations

import argparse
import csv
import json
import tempfile
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

SOURCE_URL = "https://download.geonames.org/export/zip/ES.zip"
COUNTRY = "ES"
# Galicia's four provinces: the only coverage RELY-109 ships.
PREFIXES = ("15", "27", "32", "36")
ATTRIBUTION = "Postal data: GeoNames (https://www.geonames.org), CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)"
DEFAULT_OUT = Path("src/relay/contexts/location/infrastructure/data/postal-codes-galicia.json")

# country, postal code, place name, admin1 name, admin1 code, admin2 name, admin2 code,
# admin3 name, admin3 code, latitude, longitude, accuracy
COLUMNS = (
    "country",
    "code",
    "name",
    "region",
    "region_code",
    "province",
    "province_code",
    "municipality",
    "municipality_code",
    "lat",
    "lng",
    "accuracy",
)


def download(destination: Path) -> Path:
    """Fetch the country dump and return the path of the extracted text file."""
    with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
        destination.write_bytes(response.read())
    with zipfile.ZipFile(destination) as archive:
        archive.extractall(destination.parent)
    return destination.with_suffix(".txt")


def rows_from(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)
        return [dict(zip(COLUMNS, row, strict=True)) for row in reader if len(row) == len(COLUMNS)]


def mode(values: list[str]) -> str:
    """Most frequent value; alphabetical on a tie, so the output is reproducible."""
    counts = Counter(values)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def trim(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """One entry per supported postal code.

    A code can cover a whole city and its villages, so the entry describes the best-located rows
    GeoNames has for it (highest accuracy column): their commonest name and their mean position.
    """
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["country"] == COUNTRY and row["code"].startswith(PREFIXES):
            grouped[row["code"]].append(row)

    trimmed: list[dict[str, Any]] = []
    for code in sorted(grouped):
        group = grouped[code]
        best_accuracy = max(int(row["accuracy"] or 0) for row in group)
        best = [row for row in group if int(row["accuracy"] or 0) == best_accuracy]
        municipality = mode([row["municipality"] for row in best])
        name = mode([row["name"] for row in best])
        trimmed.append(
            {
                "code": code,
                # GeoNames title-cases place names ("Santiago De Compostela"); the municipality
                # column is cased properly, so prefer it when the two name the same place.
                "name": municipality if name.casefold() == municipality.casefold() else name,
                "province": mode([row["province"] for row in best]),
                "municipality": municipality,
                "lat": round(sum(float(row["lat"]) for row in best) / len(best), 5),
                "lng": round(sum(float(row["lng"]) for row in best) / len(best), 5),
            }
        )
    return trimmed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, help="an already-downloaded ES.txt (default: download ES.zip)"
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    source = args.source
    scratch: tempfile.TemporaryDirectory[str] | None = None
    if source is None:
        scratch = tempfile.TemporaryDirectory()
        source = download(Path(scratch.name) / "ES.zip")

    trimmed = trim(rows_from(source))
    payload = {
        "attribution": ATTRIBUTION,
        "source": SOURCE_URL,
        "retrieved": date.today().isoformat(),
        "country": COUNTRY,
        "prefixes": list(PREFIXES),
        "codes": trimmed,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if scratch is not None:
        scratch.cleanup()

    by_province = Counter(entry["province"] for entry in trimmed)
    counts = ", ".join(f"{province} {n}" for province, n in sorted(by_province.items()))
    print(f"{args.out}: {len(trimmed)} postal codes ({counts})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
