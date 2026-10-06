from game_detection import is_game_running
from game_state import classify_state
from warthunder_api import fetch_json


def fetch_or_none(endpoint: str) -> object | None:
    try:
        return fetch_json(endpoint)
    except (OSError, TimeoutError, ValueError):
        return None


def main() -> None:
    try:
        game_running = is_game_running()
    except OSError:
        print("Nie można sprawdzić procesu War Thunder.")
        return

    indicators = fetch_or_none("/indicators")
    map_info = fetch_or_none("/map_info.json")
    mission = fetch_or_none("/mission.json")

    print(
        "Rozpoznany stan:",
        classify_state(game_running, indicators, map_info, mission),
    )

    if isinstance(indicators, dict):
        print("Pojazd API:", indicators.get("type", "brak"))
        print("Typ army:", indicators.get("army", "brak"))
    if isinstance(map_info, dict):
        print("Mapa dostępna:", map_info.get("valid", "brak"))
    if isinstance(mission, dict):
        objectives = mission.get("objectives")
        if isinstance(objectives, list):
            print(
                "Aktywny cel główny:",
                any(
                    isinstance(item, dict) and item.get("primary") is True
                    for item in objectives
                ),
            )
        else:
            print("Lista celów: brak")


if __name__ == "__main__":
    main()