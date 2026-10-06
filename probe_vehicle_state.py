import re
from itertools import islice

from warthunder_api import fetch_json

_KILL_FIELD_PATTERN = re.compile(r"(kill|frag|score)", re.IGNORECASE)
_MAX_CANDIDATE_NODES = 300
_MAX_CANDIDATE_HITS = 20


def _safe_key(value: object) -> str:
    text = str(value)
    escaped = "".join(
        character if character.isprintable() else f"\\u{ord(character):04x}"
        for character in text
    )
    return escaped[:80]


def show_fields(label: str, data: object, names: tuple[str, ...]) -> None:
    print(label)
    if not isinstance(data, dict):
        print("  endpoint niedostępny lub odpowiedź nie jest obiektem")
        return

    for name in names:
        if name in data:
            value = data[name]
            if isinstance(value, (str, int, float, bool)) or value is None:
                print(f"  {name}: {value!r}")
            else:
                print(f"  {name}: <{type(value).__name__}>")
        else:
            print(f"  {name}: brak")


def show_candidate_kill_fields(label: str, data: object) -> None:
    print(f"{label} pola kandydujące (kill/frag/score):")
    if not isinstance(data, (dict, list)):
        print("  niedostępne")
        return

    stack: list[tuple[str, object, int]] = [("$", data, 0)]
    visited = 0
    hits = 0
    while stack and visited < _MAX_CANDIDATE_NODES:
        path, value, depth = stack.pop()
        visited += 1
        if depth >= 5:
            continue
        if isinstance(value, dict):
            for key, child in islice(value.items(), 100):
                safe_key = _safe_key(key)
                child_path = f"{path}.{safe_key}"
                if _KILL_FIELD_PATTERN.search(safe_key) and isinstance(
                    child,
                    (str, int, float, bool),
                ):
                    display_value = repr(child)
                    if len(display_value) > 80:
                        display_value = display_value[:77] + "..."
                    print(f"  {child_path[:200]}: {display_value}")
                    hits += 1
                    if hits >= _MAX_CANDIDATE_HITS:
                        print("  wynik ograniczony")
                        return
                if isinstance(child, (dict, list)):
                    stack.append((child_path, child, depth + 1))
        elif isinstance(value, list):
            for index, child in enumerate(value[:100]):
                if isinstance(child, (dict, list)):
                    stack.append((f"{path}[{index}]", child, depth + 1))

    if not hits:
        print("  brak")
    if stack:
        print("  skan ograniczony do bezpiecznego limitu")


def main() -> None:
    try:
        indicators = fetch_json("/indicators")
    except (OSError, TimeoutError, ValueError) as error:
        print(f"/indicators niedostępny ({type(error).__name__})")
        indicators = None

    try:
        state = fetch_json("/state")
    except (OSError, TimeoutError, ValueError) as error:
        print(f"/state niedostępny ({type(error).__name__})")
        state = None

    show_fields(
        "/indicators",
        indicators,
        ("valid", "army", "type", "speed", "crew_total", "crew_current", "radio_altitude"),
    )
    show_fields(
        "/state",
        state,
        ("valid", "IAS, km/h", "TAS, km/h", "H, m", "Vy, m/s"),
    )
    show_candidate_kill_fields("/indicators", indicators)
    show_candidate_kill_fields("/state", state)


if __name__ == "__main__":
    main()