import json
import os
import re
import tempfile
from pathlib import Path
from typing import TypedDict

MAX_REGISTRY_BYTES = 256 * 1024
MAX_REGISTRY_ENTRIES = 1000
MAX_MAP_NAME_LENGTH = 120
MAX_LEVEL_ID_LENGTH = 128
FINGERPRINT_PATTERN = re.compile(r"^[0-9a-fA-F]{16}$")
LEVEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


class RegisteredMap(TypedDict):
    name: str
    level_id: str | None


def registry_path() -> Path:
    appdata = Path(os.environ.get("APPDATA") or Path.home())
    return appdata / "WarThunderRS" / "map_names.json"


def normalize_fingerprint(fingerprint: str) -> str:
    if not isinstance(fingerprint, str) or not FINGERPRINT_PATTERN.fullmatch(
        fingerprint
    ):
        raise ValueError("Fingerprint must contain exactly 16 hexadecimal digits")
    return fingerprint.casefold()


def _validate_map_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("Map display name must be text")
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ValueError("Map display name cannot contain control characters")
    normalized = " ".join(name.split())
    if not normalized or len(normalized) > MAX_MAP_NAME_LENGTH:
        raise ValueError(
            f"Map display name must be 1-{MAX_MAP_NAME_LENGTH} safe characters"
        )
    return normalized


def _validate_level_id(level_id: str | None) -> str | None:
    if level_id is None:
        return None
    if not isinstance(level_id, str) or not LEVEL_ID_PATTERN.fullmatch(level_id):
        raise ValueError(
            f"Level ID must be 1-{MAX_LEVEL_ID_LENGTH} letters, digits, '.', '_' or '-'"
        )
    return level_id


def _read_registry(path: Path) -> dict[str, RegisteredMap]:
    try:
        with path.open("rb") as registry_file:
            raw = registry_file.read(MAX_REGISTRY_BYTES + 1)
    except FileNotFoundError:
        return {}

    if len(raw) > MAX_REGISTRY_BYTES:
        raise ValueError("User map registry exceeds the configured size limit")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("User map registry is invalid JSON") from error
    if not isinstance(data, dict):
        raise ValueError("User map registry must be a JSON object")
    if len(data) > MAX_REGISTRY_ENTRIES:
        raise ValueError("User map registry exceeds the configured entry limit")

    registry: dict[str, RegisteredMap] = {}
    for raw_fingerprint, raw_entry in data.items():
        fingerprint = normalize_fingerprint(raw_fingerprint)
        if fingerprint in registry:
            raise ValueError("User map registry contains duplicate fingerprints")
        if not isinstance(raw_entry, dict) or set(raw_entry) - {"name", "level_id"}:
            raise ValueError("User map registry contains an invalid entry")
        name = _validate_map_name(raw_entry.get("name"))
        level_id = _validate_level_id(raw_entry.get("level_id"))
        registry[fingerprint] = {"name": name, "level_id": level_id}
    return registry


def find_registered_map(fingerprint: str) -> str | None:
    normalized_fingerprint = normalize_fingerprint(fingerprint)
    registry = _read_registry(registry_path())
    entry = registry.get(normalized_fingerprint)
    return entry["name"] if entry is not None else None


def register_map(
    fingerprint: str,
    name: str,
    level_id: str | None = None,
) -> None:
    normalized_fingerprint = normalize_fingerprint(fingerprint)
    normalized_name = _validate_map_name(name)
    normalized_level_id = _validate_level_id(level_id)

    path = registry_path()
    registry = _read_registry(path)
    if (
        normalized_fingerprint not in registry
        and len(registry) >= MAX_REGISTRY_ENTRIES
    ):
        raise ValueError("User map registry has reached its entry limit")
    registry[normalized_fingerprint] = {
        "name": normalized_name,
        "level_id": normalized_level_id,
    }

    serialized = json.dumps(registry, ensure_ascii=False, indent=2) + "\n"
    encoded = serialized.encode("utf-8")
    if len(encoded) > MAX_REGISTRY_BYTES:
        raise ValueError("User map registry would exceed the configured size limit")

    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=directory,
            prefix="map-names-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(encoded)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, path)
    except OSError:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
