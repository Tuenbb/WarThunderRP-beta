from urllib.parse import urlsplit

from config import (
    PRESENCE_STATE_KEYS,
    build_presence_lines,
    default_presence_profiles,
    load_presence_profiles,
)
from game_detection import is_game_running
from game_state import classify_presence_state, presence_assets_enabled
from presence_stats import extract_presence_values
from vehicle_catalog import apply_detected_nation, get_vehicle_profile
from vehicle_names import get_cached_vehicle_info
from warthunder_api import fetch_json


def _fetch(endpoint: str) -> tuple[object | None, str | None]:
    try:
        return fetch_json(endpoint), None
    except (OSError, TimeoutError, ValueError) as error:
        return None, type(error).__name__


def main() -> None:
    try:
        game_running = is_game_running()
    except OSError as error:
        game_running = False
        print("Wykrywanie gry:", type(error).__name__)
    indicators, indicators_error = _fetch("/indicators")
    state, state_error = _fetch("/state")
    map_info, map_error = _fetch("/map_info.json")
    mission, mission_error = _fetch("/mission.json")

    print("WarThunderRPC — diagnostyka Rich Presence (bez wysyłania RPC)")
    print("Gra uruchomiona:", game_running)
    for endpoint, error in (
        ("/indicators", indicators_error),
        ("/state", state_error),
        ("/map_info.json", map_error),
        ("/mission.json", mission_error),
    ):
        print(f"{endpoint}: {'dostępny' if error is None else error}")

    state_key = classify_presence_state(
        game_running,
        indicators,
        map_info,
        mission,
    )
    print("Stan:", state_key or "brak")
    assets_allowed = presence_assets_enabled(state_key)
    print("Obrazy dozwolone dla stanu:", assets_allowed)

    api_type = (
        indicators.get("type")
        if isinstance(indicators, dict)
        and indicators.get("valid") is True
        else None
    )
    print(
        "Indykator vehicle id:",
        api_type if isinstance(api_type, str) else "niedostępny",
    )
    army = (
        indicators.get("army")
        if isinstance(indicators, dict)
        and indicators.get("valid") is True
        else None
    )
    vehicle_profile = get_vehicle_profile(api_type, army)
    if vehicle_profile is None:
        print("Profil pojazdu: niedostępny")
        return

    cached_info = get_cached_vehicle_info(api_type)
    if cached_info is not None:
        vehicle_profile = apply_detected_nation(
            vehicle_profile,
            cached_info.nation_id,
        )
    print("Klasa:", vehicle_profile.vehicle_class or "nieznana")
    print("Klucz obrazu pojazdu:", vehicle_profile.vehicle_asset_key or "brak")
    image_url = vehicle_profile.vehicle_image_url
    print(
        "Host URL obrazu pojazdu:",
        urlsplit(image_url).hostname if image_url else "brak",
    )
    print("Klucz flagi:", vehicle_profile.flag_asset_key or "brak")
    flag_path = vehicle_profile.flag_image_path
    print(
        "Plik flagi istnieje:",
        bool(flag_path and flag_path.is_file()),
    )
    print(
        "Nacja dostępna z cache:",
        cached_info is not None and cached_info.nation_id is not None,
    )

    try:
        profiles = load_presence_profiles()
    except (OSError, ValueError) as error:
        print("Ustawienia profili: niedostępne", type(error).__name__)
        profiles = default_presence_profiles()
    selected_key = state_key if state_key in PRESENCE_STATE_KEYS else "loading"
    selected_profile = profiles[selected_key]
    cached_name = (
        cached_info.name
        if cached_info is not None
        else vehicle_profile.display_name
    )
    presence_values = extract_presence_values(state, cached_name)
    details, second_line = build_presence_lines(
        selected_profile,
        cached_name,
        presence_values,
    )
    print("Profil tekstu:", selected_key)
    print("Tryb drugiej linii:", selected_profile.second_line_mode)
    print("RPC details wysyłane:", details is not None)
    print("Nazwa pojazdu dostępna:", bool(cached_name))
    print("Nazwa pojazdu potwierdzona cache:", cached_info is not None)
    print("Wartość {speed} dostępna:", presence_values["speed"] is not None)
    print("Wartość {ias} dostępna:", presence_values["ias"] is not None)
    print("Wartość {tas} dostępna:", presence_values["tas"] is not None)
    print("Wartość {kills} dostępna:", presence_values["kills"] is not None)
    print("RPC state tekstowo włączone:", bool(second_line))
    print("RPC zachowa skonfigurowany Off:", second_line is None)

    large_image = (
        image_url or vehicle_profile.vehicle_asset_key
        if assets_allowed
        else None
    )
    small_image = (
        vehicle_profile.flag_asset_key if assets_allowed else None
    )
    print("Payload large_image:", large_image or "brak")
    print("Payload small_image:", small_image or "brak")
    if large_image and small_image:
        print("Kolejność fallbacku:", "pojazd+flaga → flaga → tekst")
    elif large_image:
        print("Kolejność fallbacku:", "pojazd → tekst")
    elif small_image:
        print("Kolejność fallbacku:", "flaga → tekst")
    else:
        print("Kolejność fallbacku:", "tekst")
    print(
        "RPC użyje niewidzialnego state placeholdera:",
        not second_line and bool(large_image or small_image),
    )
    if assets_allowed and image_url and not vehicle_profile.vehicle_asset_key:
        print(
            "Uwaga: brak assetu pojazdu. Jeśli Discord odrzuci URL, "
            "fallback nie może pokazać lokalnego obrazu pojazdu."
        )
    if assets_allowed and vehicle_profile.flag_asset_key:
        print(
            "Discord Portal musi zawierać dokładnie wskazany klucz flagi; "
            "lokalny plik nie potwierdza rejestracji w portalu."
        )


if __name__ == "__main__":
    main()
