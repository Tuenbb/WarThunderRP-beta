from warthunder_api import fetch_json


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


if __name__ == "__main__":
    main()