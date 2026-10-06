import math
from typing import Any


def _format_speed(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0 or value > 10_000 or not math.isfinite(value):
        return None
    return f"{value:g} km/h"


def extract_presence_values(
    state: Any,
    vehicle_name: str | None,
) -> dict[str, str | None]:
    values: dict[str, str | None] = {
        "vehicle": vehicle_name,
        "speed": None,
        "ias": None,
        "tas": None,
        "kills": None,
    }
    if not isinstance(state, dict) or state.get("valid") is not True:
        return values

    values["ias"] = _format_speed(state.get("IAS, km/h"))
    values["tas"] = _format_speed(state.get("TAS, km/h"))
    values["speed"] = values["ias"] or values["tas"]
    return values
