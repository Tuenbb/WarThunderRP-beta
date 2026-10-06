import re
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
VEHICLE_ID_PATTERN = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9_-]{0,49}/)?[A-Za-z][A-Za-z0-9_-]{0,99}$"
)
VEHICLE_IMAGE_BASE_URL = (
    "https://static.encyclopedia.warthunder.com/images/"
)


@dataclass(frozen=True)
class VehicleProfile:
    display_name: str
    vehicle_asset_key: str | None
    flag_asset_key: str | None
    vehicle_image_url: str
    flag_name: str | None = None
    vehicle_image_path: Path | None = None
    flag_image_path: Path | None = None


# Prefiks ID -> klucz assetu, lokalny plik i tekst podpowiedzi flagi.
NATION_FLAGS: tuple[tuple[str, str, str, str], ...] = (
    ("ussr_", "country_ussr", "country ussr.png", "ZSRR"),
    ("germ_", "country_germany", "country_germany.png", "Niemcy"),
    ("usa_", "country_usa", "country_usa.png", "USA"),
    ("us_", "country_usa", "country_usa.png", "USA"),
    ("uk_", "country_britain", "country_britain.png", "Wielka Brytania"),
    ("britain_", "country_britain", "country_britain.png", "Wielka Brytania"),
    ("cn_", "country_china", "country_china.png", "Chiny"),
    ("china_", "country_china", "country_china.png", "Chiny"),
    ("fr_", "country_france", "country_france.png", "Francja"),
    ("it_", "country_italy", "country_italy.png", "Włochy"),
    ("jp_", "country_japan", "country_japan.png", "Japonia"),
    ("sw_", "country_sweden", "country_sweden.png", "Szwecja"),
    ("swe_", "country_sweden", "country_sweden.png", "Szwecja"),
    ("il_", "flag_il", "country_israel.png", "Izrael"),
    ("isr_", "flag_il", "country_israel.png", "Izrael"),
)


def _nation_flag(
    model_id: str,
) -> tuple[str | None, Path | None, str | None]:
    normalized = model_id.casefold()

    for prefix, asset_key, filename, flag_name in NATION_FLAGS:
        if normalized.startswith(prefix):
            return (
                asset_key,
                PROJECT_ROOT / "assets" / "flags" / filename,
                flag_name,
            )

    return None, None, None


VEHICLE_CATALOG: dict[str, VehicleProfile] = {
    "tankModels/il_m113_hvms": VehicleProfile(
        display_name="M113A1 (HVM)",
        vehicle_asset_key="m113_hvms",
        flag_asset_key="flag_il",
        vehicle_image_url=(
            f"{VEHICLE_IMAGE_BASE_URL}il_m113_hvms.png"
        ),
        flag_name="Izrael",
        vehicle_image_path=(
            PROJECT_ROOT / "assets" / "vehicles" / "il_m113_hvms.png"
        ),
        flag_image_path=(
            PROJECT_ROOT / "assets" / "flags" / "country_israel.png"
        ),
    ),
}


def get_vehicle_profile(api_type: object) -> VehicleProfile | None:
    if not isinstance(api_type, str):
        return None

    exact_match = VEHICLE_CATALOG.get(api_type)
    if exact_match is not None:
        return exact_match

    if not VEHICLE_ID_PATTERN.fullmatch(api_type):
        return None

    model_id = api_type.rsplit("/", maxsplit=1)[-1]
    readable_name = model_id.replace("_", " ").title()
    flag_asset_key, flag_path, flag_name = _nation_flag(model_id)

    return VehicleProfile(
        display_name=readable_name,
        vehicle_asset_key=None,
        flag_asset_key=flag_asset_key,
        vehicle_image_url=f"{VEHICLE_IMAGE_BASE_URL}{model_id}.png",
        flag_name=flag_name,
        flag_image_path=flag_path,
    )