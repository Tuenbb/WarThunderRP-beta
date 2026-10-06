from game_detection import is_game_running
from vehicle_catalog import apply_detected_nation, get_vehicle_profile
from vehicle_names import resolve_vehicle_info
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
    profile = get_vehicle_profile(api_type, indicators.get("army"))

    if profile is None:
        print("Nieznany pojazd (API nie podało rozpoznanego typu).")
        return

    wiki_info = (
        resolve_vehicle_info(api_type, fallback_name(api_type))
        if profile.model_id is not None
        else None
    )
    profile = apply_detected_nation(
        profile,
        wiki_info.nation_id if wiki_info is not None else None,
    )
    display_name = (
        profile.display_name
        if profile.vehicle_asset_key is not None or wiki_info is None
        else wiki_info.name
    )
    name_source = (
        "lokalny katalog lub typ z API"
        if profile.vehicle_asset_key is not None or wiki_info is None
        else (
            "War Thunder Wiki lub lokalny cache"
            if wiki_info.name != fallback_name(api_type)
            else "awaryjna nazwa z identyfikatora"
        )
    )

    print("Typ z lokalnego API:", api_type)
    print("Nazwa wyświetlana:", display_name)
    print("Źródło nazwy:", name_source)
    print("Nacja:", profile.flag_name or "nierozpoznana")
    print("URL obrazu:", profile.vehicle_image_url)
    print("Asset pojazdu:", profile.vehicle_asset_key or "brak")
    print("Asset flagi:", profile.flag_asset_key or "brak")


if __name__ == "__main__":
    main()