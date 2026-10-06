from typing import Any


_STATE_LABELS = {
    "hangar": "Hangar",
    "loading": "Ładowanie lub dane pojazdu niedostępne",
    "battle": "Bitwa",
    "test_drive": "Test drive",
}


def _classify_state(
    game_running: bool,
    indicators: Any,
    map_info: Any,
    mission: Any,
) -> tuple[str | None, str]:
    if not game_running:
        return None, "War Thunder zamknięty"

    if not isinstance(map_info, dict):
        return "loading", "Ładowanie lub lokalne API chwilowo niedostępne"

    indicators_valid = (
        isinstance(indicators, dict) and indicators.get("valid") is True
    )
    vehicle_type = indicators.get("type") if isinstance(indicators, dict) else None
    if (
        indicators_valid
        and isinstance(vehicle_type, str)
        and vehicle_type.casefold() == "dummy_plane"
    ):
        return "loading", "Ładowanie do bitwy"

    if map_info.get("valid") is not True:
        if indicators_valid:
            return "hangar", _STATE_LABELS["hangar"]
        return "loading", _STATE_LABELS["loading"]

    objectives = mission.get("objectives") if isinstance(mission, dict) else None
    if isinstance(objectives, list) and any(
        isinstance(objective, dict) and objective.get("primary") is True
        for objective in objectives
    ):
        return "battle", _STATE_LABELS["battle"]

    if not indicators_valid:
        if not isinstance(indicators, dict):
            return "loading", "Ładowanie lub lokalne API chwilowo niedostępne"
        return "loading", _STATE_LABELS["loading"]

    return "test_drive", _STATE_LABELS["test_drive"]


def classify_presence_state(
    game_running: bool,
    indicators: Any,
    map_info: Any,
    mission: Any,
) -> str | None:
    state_key, _label = _classify_state(
        game_running,
        indicators,
        map_info,
        mission,
    )
    return state_key


def presence_assets_enabled(state_key: str | None) -> bool:
    return state_key in {"hangar", "battle", "test_drive"}


def classify_state(
    game_running: bool,
    indicators: Any,
    map_info: Any,
    mission: Any,
) -> str:
    _state_key, label = _classify_state(
        game_running,
        indicators,
        map_info,
        mission,
    )
    return label