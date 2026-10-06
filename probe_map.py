import json
import sys
from collections.abc import Iterable, Mapping
from typing import TextIO
from urllib.error import HTTPError, URLError

from warthunder_api import (
    ApiResponseError,
    ENDPOINTS,
    ResponseTooLargeError,
    fetch_json_data,
)

MAP_PROBE_ENDPOINTS = ("/state", "/map_info.json", "/map_obj.json", "/indicators")
CANDIDATE_KEYS = frozenset(
    {"map_id", "name", "map_name", "location", "level", "zone_id"}
)
MAX_CANDIDATE_HITS = 2
MAX_TRAVERSED_NODES = 20_000
MAX_NESTING_DEPTH = 8
MAX_PATH_LENGTH = 55
MAX_VALUE_LENGTH = 45
MAX_SAMPLE_RECORDS = 3
MAX_SAMPLE_FIELDS = 4
MAX_SUMMARY_FIELDS = 6
MAX_KEY_LENGTH = 28
MAX_SAMPLE_JSON_LENGTH = 100
_SAFE_ENDPOINTS = frozenset(ENDPOINTS)


def _safe_error(error: BaseException) -> str:
    if isinstance(error, HTTPError):
        return f"HTTP {error.code}"
    if isinstance(error, ResponseTooLargeError):
        return "response exceeded configured byte limit"
    if isinstance(error, ApiResponseError):
        return error.reason[:120]
    if isinstance(error, URLError):
        reason = error.reason
        if isinstance(reason, TimeoutError):
            return "connection timed out"
        return type(reason).__name__
    if isinstance(error, TimeoutError):
        return "connection timed out"
    if isinstance(error, OSError):
        return type(error).__name__
    if isinstance(error, json.JSONDecodeError):
        return f"invalid JSON (line {error.lineno}, column {error.colno})"
    return type(error).__name__


def _type_name(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def _short_value(value: object) -> str:
    rendered = json.dumps(value, ensure_ascii=True)
    if len(rendered) > MAX_VALUE_LENGTH:
        return rendered[: MAX_VALUE_LENGTH - 3] + "..."
    return rendered


def _short_path(path: str) -> str:
    rendered = json.dumps(path, ensure_ascii=True)[1:-1]
    if len(rendered) > MAX_PATH_LENGTH:
        return "..." + rendered[-(MAX_PATH_LENGTH - 3) :]
    return rendered


def _short_key(key: object) -> str:
    rendered = json.dumps(str(key), ensure_ascii=True)
    if len(rendered) > MAX_KEY_LENGTH:
        return rendered[: MAX_KEY_LENGTH - 3] + "..."
    return rendered


def _candidate_fields(data: object) -> tuple[list[tuple[str, object]], bool]:
    matches: list[tuple[str, object]] = []
    stack: list[tuple[object, str, int]] = [(data, "$", 0)]
    visited = 0
    truncated = False

    while stack and visited < MAX_TRAVERSED_NODES and len(matches) < MAX_CANDIDATE_HITS:
        value, path, depth = stack.pop()
        visited += 1

        if depth >= MAX_NESTING_DEPTH:
            if isinstance(value, (Mapping, list)):
                truncated = True
            continue
        if isinstance(value, Mapping):
            children = list(value.items())
            capacity = MAX_TRAVERSED_NODES - visited - len(stack)
            if len(children) > capacity:
                truncated = True
            for index in reversed(range(min(len(children), max(0, capacity)))):
                key, child = children[index]
                key_text = str(key)
                child_path = (
                    f"{path}.{key_text}"
                    if key_text.isidentifier()
                    else f"{path}[{json.dumps(key_text, ensure_ascii=True)}]"
                )
                if key_text.casefold() in CANDIDATE_KEYS and not isinstance(
                    child, (Mapping, list)
                ):
                    matches.append((_short_path(child_path), child))
                    if len(matches) >= MAX_CANDIDATE_HITS:
                        truncated = truncated or index > 0 or bool(stack)
                        break
                elif isinstance(child, (Mapping, list)):
                    stack.append((child, child_path, depth + 1))
        elif isinstance(value, list):
            capacity = MAX_TRAVERSED_NODES - visited - len(stack)
            if len(value) > capacity:
                truncated = True
            for index in reversed(range(min(len(value), max(0, capacity)))):
                stack.append((value[index], f"{path}[{index}]", depth + 1))

    return matches, truncated or bool(stack)


def _print_object_structure(data: Mapping[object, object], output: TextIO) -> None:
    print(f"Response fields ({len(data)}):", file=output)
    for key, value in list(data.items())[:MAX_SUMMARY_FIELDS]:
        print(f"  {_short_key(key)}: {_type_name(value)}", file=output)
    if len(data) > MAX_SUMMARY_FIELDS:
        print(f"  ... {len(data) - MAX_SUMMARY_FIELDS} fields omitted", file=output)


def _print_map_object_structure(data: object, output: TextIO) -> None:
    if not isinstance(data, list):
        print(f"Response structure: {_type_name(data)}", file=output)
        if isinstance(data, Mapping):
            _print_object_structure(data, output)
        return

    print(f"Response structure: array ({len(data)} items)", file=output)
    for index, item in enumerate(data[:MAX_SAMPLE_RECORDS]):
        print(f"Item {index}:", file=output)
        if isinstance(item, Mapping):
            visible_fields = list(item.items())[:MAX_SAMPLE_FIELDS]
            keys = ", ".join(
                f"{_short_key(key)}:{_type_name(value)}"
                for key, value in visible_fields
            )
            print(f"  fields ({len(item)}): {keys}", file=output)
            if len(item) > MAX_SAMPLE_FIELDS:
                print(f"  ... {len(item) - MAX_SAMPLE_FIELDS} fields omitted", file=output)
        else:
            print(f"  value type: {_type_name(item)}", file=output)
        sample = json.dumps(item, ensure_ascii=True, separators=(",", ":"))
        if len(sample) > MAX_SAMPLE_JSON_LENGTH:
            sample = sample[: MAX_SAMPLE_JSON_LENGTH - 3] + "..."
        print(f"  sample: {sample}", file=output)
    if len(data) > MAX_SAMPLE_RECORDS:
        print(f"... {len(data) - MAX_SAMPLE_RECORDS} more items omitted", file=output)


def print_endpoint_responses(
    endpoints: Iterable[str] = MAP_PROBE_ENDPOINTS,
    output: TextIO = sys.stdout,
) -> None:
    for endpoint in endpoints:
        print(f"=== {endpoint} ===", file=output)
        if endpoint not in _SAFE_ENDPOINTS or endpoint not in MAP_PROBE_ENDPOINTS:
            print("Error: endpoint is not allowed by this probe", file=output)
            continue

        try:
            data = fetch_json_data(endpoint)
        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
            json.JSONDecodeError,
            ApiResponseError,
            ResponseTooLargeError,
        ) as error:
            print(f"Error: {_safe_error(error)}", file=output)
            print("Candidate fields found: unavailable", file=output)
            continue

        if endpoint == "/map_obj.json":
            _print_map_object_structure(data, output)
        elif isinstance(data, Mapping):
            _print_object_structure(data, output)
        else:
            print(f"Response structure: {_type_name(data)}", file=output)

        matches, truncated = _candidate_fields(data)
        print(f"Candidate fields found: {'yes' if matches else 'no'}", file=output)
        for path, value in matches:
            print(f"  {path} = {_short_value(value)}", file=output)
        if truncated:
            print("  ... candidate search truncated at configured limit", file=output)


def main() -> None:
    print_endpoint_responses()


if __name__ == "__main__":
    main()
