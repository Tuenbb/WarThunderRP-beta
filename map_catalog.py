import json
import logging
import re
from collections.abc import Mapping
from pathlib import Path

from user_map_registry import find_registered_map

CATALOG_PATH = Path(__file__).resolve().parent / "map_catalog.json"
FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{16}$")
logger = logging.getLogger(__name__)
_MAP_NAME_KEYS = (
    "mapname",
    "maptitle",
    "levelname",
    "locationname",
    "map",
    "name",
    "title",
)
_MISSION_MAP_NAME_KEYS = (
    "mapname",
    "maptitle",
    "levelname",
    "locationname",
    "map",
)
_MAP_CONTAINERS = (
    "mapinfo",
    "map",
    "level",
    "location",
    "mission",
    "scenario",
)


def find_map_name(fingerprint: str) -> str | None:
    if not FINGERPRINT_PATTERN.fullmatch(fingerprint):
        raise ValueError("Nieprawidłowy format odcisku mapy")

    try:
        registered_name = find_registered_map(fingerprint)
    except (OSError, ValueError) as error:
        logger.warning(
            "Could not read user map registry (%s)",
            type(error).__name__,
        )
    else:
        if registered_name is not None:
            return registered_name

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


def _normalized_key(key: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).casefold())


def _valid_map_title(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    title = " ".join(value.split())
    if not title or len(title) > 120 or any(ord(char) < 32 for char in title):
        return None
    return title


def _named_value(
    source: Mapping[object, object],
    accepted_keys: tuple[str, ...],
) -> str | None:
    for accepted_key in accepted_keys:
        for key, value in source.items():
            if _normalized_key(key) == accepted_key:
                title = _valid_map_title(value)
                if title is not None:
                    return title
    return None


def find_map_name_from_metadata(
    map_info: object,
    mission: object,
) -> str | None:
    if isinstance(map_info, Mapping) and map_info.get("valid") is not False:
        title = _named_value(map_info, _MAP_NAME_KEYS)
        if title is not None:
            return title

        for container in _MAP_CONTAINERS:
            for key, value in map_info.items():
                if (
                    _normalized_key(key) == container
                    and isinstance(value, Mapping)
                ):
                    title = _named_value(value, _MAP_NAME_KEYS)
                    if title is not None:
                        return title

    if isinstance(mission, Mapping) and mission.get("valid") is not False:
        title = _named_value(mission, _MISSION_MAP_NAME_KEYS)
        if title is not None:
            return title

        for container in _MAP_CONTAINERS:
            for key, value in mission.items():
                if (
                    _normalized_key(key) == container
                    and isinstance(value, Mapping)
                ):
                    title = _named_value(value, _MAP_NAME_KEYS)
                    if title is not None:
                        return title

    return None