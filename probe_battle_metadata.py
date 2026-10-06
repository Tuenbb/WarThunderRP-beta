import json
import re
from collections.abc import Mapping, Sequence
from urllib.error import HTTPError, URLError

from warthunder_api import ApiResponseError, fetch_json_data

MAX_SCHEMA_NODES = 160
MAX_SCHEMA_DEPTH = 5
MAX_CHILDREN = 8
MAX_TEXT_LENGTH = 120
MAX_MISSION_TEXT_LENGTH = 160
MAX_SUMMARY_VALUES = 16
MAX_SUMMARY_FIELDS = 32
MAP_METADATA_FIELDS = frozenset(
    {
        "map",
        "mapname",
        "name",
        "mapid",
        "location",
        "level",
        "mission",
        "scenario",
    }
)
MISSION_MAP_FIELDS = frozenset(
    {"map", "mapname", "maptitle", "levelname", "locationname"}
)
MAP_CONTAINERS = frozenset(
    {"map", "mapinfo", "level", "location", "mission", "scenario"}
)
SAFE_BOOLEAN_FIELDS = frozenset({"valid", "primary", "active", "isplayer", "player"})
CLASSIFICATION_FIELDS = frozenset({"army", "type", "class", "kind"})
FIELD_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z_]{0,49}$")


def _normalized_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _is_map_metadata_field(
    endpoint: str,
    depth: int,
    normalized_key: str,
    parent_path: str,
) -> bool:
    if endpoint == "/map_info.json":
        path_segments = {
            _normalized_key(segment.split("[", maxsplit=1)[0])
            for segment in parent_path.split(".")
        }
        return (
            depth == 0 and normalized_key in MAP_METADATA_FIELDS
        ) or (
            depth > 0
            and normalized_key in {"name", "title", "mapname", "maptitle"}
            and bool(path_segments.intersection(MAP_CONTAINERS))
        )
    if endpoint == "/mission.json":
        path_segments = {
            _normalized_key(segment.split("[", maxsplit=1)[0])
            for segment in parent_path.split(".")
        }
        return (
            depth == 0 and normalized_key in MISSION_MAP_FIELDS
        ) or (
            depth > 0
            and normalized_key in {"name", "title", "mapname", "maptitle"}
            and bool(path_segments.intersection(MAP_CONTAINERS))
        )
    return False


def _safe_text(value: str, limit: int = MAX_MISSION_TEXT_LENGTH) -> str:
    clipped = value[:limit]
    if len(value) > limit:
        clipped += "..."
    return json.dumps(clipped, ensure_ascii=True)


def _safe_error_reason(error: BaseException) -> str:
    if isinstance(error, HTTPError):
        reason = error.reason
        status_text = reason if isinstance(reason, str) else type(reason).__name__
        return f"HTTP {error.code} {_safe_text(status_text, 80)}"
    if isinstance(error, ApiResponseError):
        return _safe_text(error.reason, 100)
    if isinstance(error, OSError):
        errno = f", errno={error.errno}" if error.errno is not None else ""
        return f"{type(error).__name__}{errno}"
    if isinstance(error, URLError):
        return type(error).__name__
    return type(error).__name__


def _summarize_map_objects(data: list[object]) -> list[str]:
    type_counts: dict[str, int] = {}
    field_types: dict[str, set[str]] = {}
    player_markers: dict[str, int] = {}

    for item in data:
        if not isinstance(item, Mapping):
            continue

        for key, value in item.items():
            normalized = _normalized_key(key)
            raw_name = str(key)
            name = (
                raw_name
                if FIELD_NAME_PATTERN.fullmatch(raw_name)
                else "<dynamic-key>"
            )

            if normalized == "type" and isinstance(value, str):
                safe_type = value[:MAX_TEXT_LENGTH]
                type_counts[safe_type] = type_counts.get(safe_type, 0) + 1

            if normalized in {
                "isplayer",
                "player",
                "is_player",
                "islocalplayer",
                "iscontrolled",
                "playercontrolled",
                "controlledbyplayer",
            }:
                if isinstance(value, bool):
                    player_markers[name] = player_markers.get(name, 0) + 1

            if name != "<dynamic-key>":
                values = field_types.setdefault(name, set())
                values.add(type(value).__name__)

    lines = [
        f"  map_object_count={len(data)}, "
        f"object_record_count={sum(isinstance(item, Mapping) for item in data)}"
    ]
    if type_counts:
        top_types = sorted(type_counts.items(), key=lambda pair: (-pair[1], pair[0]))
        formatted_types = ", ".join(
            f"{_safe_text(name, MAX_TEXT_LENGTH)}: {count}"
            for name, count in top_types[:MAX_SUMMARY_VALUES]
        )
        if len(top_types) > MAX_SUMMARY_VALUES:
            formatted_types += ", ..."
        lines.append(f"  object_types={formatted_types}")

    if field_types:
        fields = sorted(field_types.items())
        formatted_fields = ", ".join(
            f"{name}({'/'.join(sorted(value_types))})"
            for name, value_types in fields[:MAX_SUMMARY_FIELDS]
        )
        if len(fields) > MAX_SUMMARY_FIELDS:
            formatted_fields += ", ..."
        lines.append(f"  observed_fields={formatted_fields}")

    if player_markers:
        formatted_markers = ", ".join(
            f"{name}={count}" for name, count in sorted(player_markers.items())
        )
        lines.append(f"  explicit_player_boolean_fields={formatted_markers}")
    else:
        lines.append("  explicit_player_boolean_fields=none")

    return lines


def _shape_lines(
    value: object,
    path: str,
    *,
    endpoint: str,
    budget: list[int],
    depth: int = 0,
) -> list[str]:
    if budget[0] <= 0:
        return [f"{path}: <schema output capped>"]
    budget[0] -= 1

    if isinstance(value, Mapping):
        lines = [f"{path}: object ({len(value)} keys)"]
        if depth >= MAX_SCHEMA_DEPTH:
            return lines
        for index, (key, child) in enumerate(value.items()):
            if index >= MAX_CHILDREN:
                lines.append(f"{path}: <remaining keys omitted>")
                break
            field_name = str(key)
            safe_field_name = (
                field_name
                if FIELD_NAME_PATTERN.fullmatch(field_name)
                else "<dynamic-key>"
            )
            child_path = f"{path}.{safe_field_name}"
            normalized = _normalized_key(key)
            if _is_map_metadata_field(endpoint, depth, normalized, path):
                if isinstance(child, str):
                    lines.append(
                        f"{child_path}: {child[:MAX_TEXT_LENGTH]!r}"
                    )
                elif isinstance(child, (int, float, bool)) or child is None:
                    lines.append(f"{child_path}: {child!r}")
            if (
                isinstance(child, bool)
                and normalized in SAFE_BOOLEAN_FIELDS
            ):
                lines.append(f"{child_path}: {child!r}")
            elif (
                isinstance(child, str)
                and normalized in CLASSIFICATION_FIELDS
            ):
                lines.append(f"{child_path}: {child[:MAX_TEXT_LENGTH]!r}")
            lines.extend(
                _shape_lines(
                    child,
                    child_path,
                    endpoint=endpoint,
                    budget=budget,
                    depth=depth + 1,
                )
            )
        return lines

    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        lines = [f"{path}: array ({len(value)} items)"]
        if depth >= MAX_SCHEMA_DEPTH:
            return lines
        for index, child in enumerate(value[:MAX_CHILDREN]):
            lines.extend(
                _shape_lines(
                    child,
                    f"{path}[{index}]",
                    endpoint=endpoint,
                    budget=budget,
                    depth=depth + 1,
                )
            )
        if len(value) > MAX_CHILDREN:
            lines.append(f"{path}: <remaining items omitted>")
        return lines

    return [f"{path}: {type(value).__name__}"]


def describe_endpoint(path: str, data: object) -> list[str]:
    lines = [path]
    if not isinstance(data, (dict, list)):
        lines.append("  endpoint unavailable or response is not an object")
        return lines

    lines.extend(
        f"  {line}"
        for line in _shape_lines(
            data,
            "$",
            endpoint=path,
            budget=[MAX_SCHEMA_NODES],
        )
    )

    if path == "/map_obj.json" and isinstance(data, list):
        lines.extend(_summarize_map_objects(data))

    if path == "/mission.json" and isinstance(data, dict):
        status = data.get("status")
        if isinstance(status, str):
            lines.append(f"  status={_safe_text(status)}")
        elif status is not None:
            lines.append(f"  status_type={type(status).__name__}")

        objectives = data.get("objectives")
        if isinstance(objectives, list):
            primary_count = sum(
                isinstance(item, dict) and item.get("primary") is True
                for item in objectives
            )
            lines.append(
                f"  objective_count={len(objectives)}, "
                f"active_primary_count={primary_count}"
            )
            for index, objective in enumerate(objectives[:MAX_CHILDREN]):
                if not isinstance(objective, dict):
                    continue
                text = objective.get("text")
                if isinstance(text, str):
                    lines.append(
                        f"  objectives[{index}].text={_safe_text(text)}"
                    )
                elif text is not None:
                    lines.append(
                        "  objectives"
                        f"[{index}].text_type={type(text).__name__}"
                    )
            if len(objectives) > MAX_CHILDREN:
                lines.append(
                    "  additional objective text omitted "
                    f"({len(objectives) - MAX_CHILDREN})"
                )

    return lines


def main() -> None:
    for endpoint in ("/map_info.json", "/mission.json", "/map_obj.json"):
        try:
            data = fetch_json_data(endpoint)
        except (OSError, TimeoutError, ValueError) as error:
            print(f"{endpoint}: unavailable ({_safe_error_reason(error)})")
            continue

        for line in describe_endpoint(endpoint, data):
            print(line)


if __name__ == "__main__":
    main()
