from typing import Any


def classify_state(
    game_running: bool,
    indicators: Any,
    map_info: Any,
    mission: Any,
) -> str:
    if not game_running:
        return "War Thunder zamknięty"

    if not isinstance(indicators, dict) or not isinstance(map_info, dict):
        return "Ładowanie lub lokalne API chwilowo niedostępne"

    if indicators.get("valid") is not True:
        return "Ładowanie lub dane pojazdu niedostępne"

    if map_info.get("valid") is not True:
        return "Hangar"

    vehicle_type = indicators.get("type")
    if isinstance(vehicle_type, str) and vehicle_type.casefold() == "dummy_plane":
        return "Ładowanie do bitwy"

    objectives = mission.get("objectives") if isinstance(mission, dict) else None
    if not isinstance(objectives, list):
        return "Test drive"

    if any(
        isinstance(objective, dict) and objective.get("primary") is True
        for objective in objectives
    ):
        return "Bitwa"

    return "Na mapie — cel misji nierozpoznany"