import time

from warthunder_api import fetch_json


def read_snapshot() -> tuple[object, ...]:
    indicators = fetch_json("/indicators")
    map_info = fetch_json("/map_info.json")
    mission = fetch_json("/mission.json")

    if not isinstance(indicators, dict):
        indicators = {}
    if not isinstance(map_info, dict):
        map_info = {}
    if not isinstance(mission, dict):
        mission = {}

    objectives = mission.get("objectives")
    if isinstance(objectives, list):
        primary_flags = tuple(
            item.get("primary")
            for item in objectives[:5]
            if isinstance(item, dict)
        )
    else:
        primary_flags = None

    return (
        indicators.get("valid"),
        indicators.get("army"),
        indicators.get("type"),
        map_info.get("valid"),
        primary_flags,
    )


def main() -> None:
    print(
        "Przez 90 sekund obserwuję lokalne API. "
        "Teraz przejdź z hangaru do bitwy."
    )
    previous = None
    deadline = time.monotonic() + 90

    while time.monotonic() < deadline:
        try:
            snapshot = read_snapshot()
            if snapshot != previous:
                print(
                    "Zmiana: "
                    f"indicators.valid={snapshot[0]!r}, "
                    f"army={snapshot[1]!r}, "
                    f"type={snapshot[2]!r}, "
                    f"map_info.valid={snapshot[3]!r}, "
                    f"objective.primary={snapshot[4]!r}"
                )
                previous = snapshot
        except (OSError, TimeoutError, ValueError) as error:
            print(f"API chwilowo niedostępne ({type(error).__name__})")

        time.sleep(3)

    print("Koniec obserwacji.")


if __name__ == "__main__":
    main()