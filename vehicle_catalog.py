import re
from dataclasses import dataclass, replace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
VEHICLE_ID_PATTERN = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9_-]{0,49}/){0,2}"
    r"[A-Za-z][A-Za-z0-9_-]{0,99}$"
)
VEHICLE_IMAGE_BASE_URL = (
    "https://static.encyclopedia.warthunder.com/images/"
)

VEHICLE_CATEGORY_CLASSES = {
    "tankmodels": "ground",
    "tank": "ground",
    "ground": "ground",
    "groundvehicles": "ground",
    "aircraft": "aircraft",
    "aircrafts": "aircraft",
    "aircraftmodels": "aircraft",
    "helicopter": "helicopter",
    "helicopters": "helicopter",
    "helicoptermodels": "helicopter",
    "ship": "naval",
    "ships": "naval",
    "shipmodels": "naval",
    "boat": "naval",
    "boats": "naval",
    "boatmodels": "naval",
    "submarines": "naval",
    "naval": "naval",
}
ARMY_CLASSES = {
    "tank": "ground",
    "ground": "ground",
    "ground_vehicle": "ground",
    "air": "air",
    "aircraft": "aircraft",
    "helicopter": "helicopter",
    "ship": "naval",
    "boat": "naval",
    "naval": "naval",
}
UNKNOWN_CLASS_NAMES = {
    "ground": "Nieznany pojazd naziemny",
    "air": "Nieznany pojazd powietrzny",
    "aircraft": "Nieznany samolot",
    "helicopter": "Nieznany śmigłowiec",
    "naval": "Nieznany okręt",
}


@dataclass(frozen=True)
class VehicleProfile:
    display_name: str
    vehicle_asset_key: str | None
    flag_asset_key: str | None
    vehicle_image_url: str | None
    flag_name: str | None = None
    vehicle_image_path: Path | None = None
    flag_image_path: Path | None = None
    nation_id: str | None = None
    flag_emoji: str | None = None
    vehicle_class: str | None = None
    model_id: str | None = None


@dataclass(frozen=True)
class NationProfile:
    nation_id: str
    name: str
    flag_emoji: str
    flag_asset_key: str | None = None
    flag_image_path: Path | None = None


def _nation(
    nation_id: str,
    name: str,
    flag_emoji: str,
    flag_filename: str | None = None,
) -> NationProfile:
    return NationProfile(
        nation_id=nation_id,
        name=name,
        flag_emoji=flag_emoji,
        flag_asset_key=(
            Path(flag_filename).stem if flag_filename is not None else None
        ),
        flag_image_path=(
            PROJECT_ROOT / "assets" / "flags" / flag_filename
            if flag_filename is not None
            else None
        ),
    )


_USA = _nation("usa", "USA", "🇺🇸", "country_usa.png")
_GERMANY = _nation(
    "germany", "Niemcy", "🇩🇪", "country_germany.png"
)
_USSR = _nation("ussr", "ZSRR", "🇷🇺", "country_ussr.png")
_BRITAIN = _nation(
    "britain", "Wielka Brytania", "🇬🇧", "country_britain.png"
)
_JAPAN = _nation("japan", "Japonia", "🇯🇵", "country_japan.png")
_CHINA = _nation("china", "Chiny", "🇨🇳", "country_china.png")
_ITALY = _nation("italy", "Włochy", "🇮🇹", "country_italy.png")
_FRANCE = _nation("france", "Francja", "🇫🇷", "country_france.png")
_SWEDEN = _nation("sweden", "Szwecja", "🇸🇪", "country_sweden.png")
_ISRAEL = _nation("israel", "Izrael", "🇮🇱", "country_israel.png")
_POLAND = _nation("poland", "Polska", "🇵🇱")
_CZECHIA = _nation("czech", "Czechy", "🇨🇿")
_HUNGARY = _nation("hungary", "Węgry", "🇭🇺")
_AUSTRIA = _nation("austria", "Austria", "🇦🇹")
_FINLAND = _nation("finland", "Finlandia", "🇫🇮")
_SOUTH_AFRICA = _nation("south_africa", "RPA", "🇿🇦")

_NATION_ALIASES: dict[str, NationProfile] = {
    alias: nation
    for nation, aliases in (
        (_USA, ("usa", "united_states", "united_states_of_america")),
        (_GERMANY, ("germany", "germ")),
        (_USSR, ("ussr", "sov", "soviet_union")),
        (_BRITAIN, ("britain", "uk", "united_kingdom", "great_britain")),
        (_JAPAN, ("japan", "jp")),
        (_CHINA, ("china", "cn")),
        (_ITALY, ("italy", "it")),
        (_FRANCE, ("france", "fr")),
        (_SWEDEN, ("sweden", "sw", "swe")),
        (_ISRAEL, ("israel", "isr", "il")),
        (_POLAND, ("poland", "pol")),
        (_CZECHIA, ("czech", "czech_republic", "czechoslovakia", "cz")),
        (_HUNGARY, ("hungary", "hu")),
        (_AUSTRIA, ("austria", "aus")),
        (_FINLAND, ("finland", "fi")),
        (_SOUTH_AFRICA, ("south_africa", "southafrica", "za")),
    )
    for alias in aliases
}


def get_nation_profile(nation_id: object) -> NationProfile | None:
    if not isinstance(nation_id, str):
        return None
    normalized = nation_id.strip().casefold()
    if normalized.startswith("country_"):
        normalized = normalized.removeprefix("country_")
    return _NATION_ALIASES.get(normalized)


def apply_detected_nation(
    profile: VehicleProfile,
    nation_id: object,
) -> VehicleProfile:
    nation = get_nation_profile(nation_id)
    if nation is None:
        return profile

    return VehicleProfile(
        display_name=profile.display_name,
        vehicle_asset_key=profile.vehicle_asset_key,
        flag_asset_key=nation.flag_asset_key,
        vehicle_image_url=profile.vehicle_image_url,
        flag_name=nation.name,
        vehicle_image_path=profile.vehicle_image_path,
        flag_image_path=nation.flag_image_path,
        nation_id=nation.nation_id,
        flag_emoji=nation.flag_emoji,
        vehicle_class=profile.vehicle_class,
        model_id=profile.model_id,
    )


VEHICLE_CATALOG: dict[str, VehicleProfile] = {
    "tankModels/il_m113_hvms": VehicleProfile(
        display_name="M113A1 (HVM)",
        vehicle_asset_key="m113_hvms",
        flag_asset_key="country_israel",
        vehicle_image_url=(
            f"{VEHICLE_IMAGE_BASE_URL}il_m113_hvms.png"
        ),
        flag_name="Izrael",
        nation_id="israel",
        flag_emoji="🇮🇱",
        vehicle_class="ground",
        model_id="il_m113_hvms",
        vehicle_image_path=(
            PROJECT_ROOT / "assets" / "vehicles" / "il_m113_hvms.png"
        ),
        flag_image_path=(
            PROJECT_ROOT / "assets" / "flags" / "country_israel.png"
        ),
    ),
}


def _vehicle_class(api_type: str | None, army: object) -> str | None:
    if isinstance(api_type, str):
        for category in api_type.split("/")[:-1]:
            detected_class = VEHICLE_CATEGORY_CLASSES.get(category.casefold())
            if detected_class is not None:
                return detected_class

    if isinstance(army, str):
        return ARMY_CLASSES.get(army.strip().casefold())
    return None


def get_vehicle_profile(
    api_type: object,
    army: object = None,
) -> VehicleProfile | None:
    valid_api_type = (
        api_type
        if isinstance(api_type, str) and VEHICLE_ID_PATTERN.fullmatch(api_type)
        else None
    )
    vehicle_class = _vehicle_class(valid_api_type, army)

    if valid_api_type is None:
        if vehicle_class is None:
            return None
        return VehicleProfile(
            display_name=UNKNOWN_CLASS_NAMES[vehicle_class],
            vehicle_asset_key=None,
            flag_asset_key=None,
            vehicle_image_url=None,
            vehicle_class=vehicle_class,
        )

    exact_match = VEHICLE_CATALOG.get(valid_api_type)
    if exact_match is not None:
        if exact_match.vehicle_class is not None:
            return exact_match
        return replace(
            exact_match,
            vehicle_class=vehicle_class,
            model_id=valid_api_type.rsplit("/", maxsplit=1)[-1],
        )

    model_id = valid_api_type.rsplit("/", maxsplit=1)[-1]
    readable_name = model_id.replace("_", " ").title()
    return VehicleProfile(
        display_name=readable_name,
        vehicle_asset_key=None,
        flag_asset_key=None,
        vehicle_image_url=f"{VEHICLE_IMAGE_BASE_URL}{model_id}.png",
        vehicle_class=vehicle_class,
        model_id=model_id,
    )