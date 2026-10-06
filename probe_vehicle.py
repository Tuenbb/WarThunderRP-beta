from game_detection import is_game_running
from vehicle_catalog import get_vehicle_profile
from vehicle_names import resolve_vehicle_name
from warthunder_api import fetch_json


def fallback_name(api_type: object) -> str:
    if not isinstance(api_type, str):
        return "Nieznany pojazd"
    model_id = api_type.rsplit("/", maxsplit=1)[-1]
    return model_id.replace("_", " ").title()


def main() -> None:
    try:
        if not is_game_running():
            print("War Thunder niewykryty.")
            return
        indicators = fetch_json("/indicators")
    except (OSError, TimeoutError, ValueError) as error:
        print(f"Nie można odczytać gry/API ({type(error).__name__})")
        return

    if not isinstance(indicators, dict) or indicators.get("valid") is not True:
        print("API nie udostępnia teraz danych pojazdu.")
        return

    api_type = indicators.get("type")
    profile = get_vehicle_profile(api_type)

    if profile is None:
        print("Identyfikator pojazdu jest nieprawidłowy.")
        return

    if profile.vehicle_asset_key is not None:
        display_name = profile.display_name
        name_source = "lokalny katalog"
    else:
        fallback = fallback_name(api_type)
        display_name = resolve_vehicle_name(api_type, fallback)
        name_source = (
            "War Thunder Wiki lub lokalny cache"
            if display_name != fallback
            else "awaryjna nazwa z identyfikatora"
        )

    print("Typ z lokalnego API:", api_type)
    print("Nazwa wyświetlana:", display_name)
    print("Źródło nazwy:", name_source)
    print("URL obrazu:", profile.vehicle_image_url)
    print("Asset pojazdu:", profile.vehicle_asset_key or "brak")
    print("Asset flagi:", profile.flag_asset_key or "brak")


if __name__ == "__main__":
    main()