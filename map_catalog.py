import json
import re
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parent / "map_catalog.json"
FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{16}$")


def find_map_name(fingerprint: str) -> str | None:
    if not FINGERPRINT_PATTERN.fullmatch(fingerprint):
        raise ValueError("Nieprawidłowy format odcisku mapy")

    raw = CATALOG_PATH.read_text(encoding="utf-8")
    catalog = json.loads(raw)

    if not isinstance(catalog, dict):
        raise ValueError("Katalog map musi być obiektem JSON")

    for key, name in catalog.items():
        if not isinstance(key, str) or not FINGERPRINT_PATTERN.fullmatch(key):
            raise ValueError("Katalog zawiera nieprawidłowy odcisk")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Katalog zawiera pustą lub nieprawidłową nazwę mapy")

    result = catalog.get(fingerprint)
    return result if isinstance(result, str) else None