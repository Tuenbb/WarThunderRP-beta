import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from config import APP_NAME, APP_VERSION
from game_detection import is_game_running
from game_state import classify_presence_state
from map_catalog import find_map_name_from_metadata
from vehicle_catalog import get_vehicle_profile
from warthunder_api import ENDPOINTS, fetch_json_data

MAX_REPORT_BYTES = 32 * 1024
DIAGNOSTIC_ENDPOINTS = ENDPOINTS


def _safe_fetch(fetcher: Callable[[str], Any], endpoint: str) -> tuple[Any, str | None]:
    try:
        return fetcher(endpoint), None
    except (OSError, TimeoutError, ValueError) as error:
        return None, type(error).__name__


def build_diagnostic_report(
    *,
    fetcher: Callable[[str], Any] = fetch_json_data,
    game_detector: Callable[[], bool] = is_game_running,
    now: datetime | None = None,
) -> dict[str, Any]:
    endpoints: dict[str, Any] = {}
    payloads: dict[str, Any] = {}
    for endpoint in DIAGNOSTIC_ENDPOINTS:
        payload, error_class = _safe_fetch(fetcher, endpoint)
        payloads[endpoint] = payload
        endpoints[endpoint] = {
            "reachable": error_class is None,
            "error_class": error_class,
        }

    try:
        game_running: bool | None = game_detector()
        detection_error = None
    except OSError as error:
        game_running = None
        detection_error = type(error).__name__

    indicators = payloads["/indicators"]
    map_info = payloads["/map_info.json"]
    mission = payloads["/mission.json"]
    state_key = classify_presence_state(
        game_running is True,
        indicators,
        map_info,
        mission,
    )

    indicators_valid = (
        isinstance(indicators, dict) and indicators.get("valid") is True
    )
    vehicle_id = indicators.get("type") if indicators_valid else None
    army = indicators.get("army") if indicators_valid else None
    vehicle_profile = get_vehicle_profile(vehicle_id, army)
    vehicle_known = bool(
        vehicle_profile is not None and vehicle_profile.model_id is not None
    )

    map_known = find_map_name_from_metadata(map_info, mission) is not None

    vehicle_url = (
        vehicle_profile.vehicle_image_url
        if vehicle_profile is not None
        else None
    )
    report_time = now or datetime.now(timezone.utc)
    return {
        "schema_version": 1,
        "application": {"name": APP_NAME, "version": APP_VERSION},
        "runtime": {
            "python": platform.python_version(),
            "operating_system": platform.system(),
            "os_release": platform.release(),
        },
        "generated_at_utc": report_time.astimezone(timezone.utc).isoformat(),
        "game_running": game_running,
        "game_detection_error_class": detection_error,
        "endpoints": endpoints,
        "presence_state": state_key,
        "vehicle": {
            "known": vehicle_known,
            "class": (
                vehicle_profile.vehicle_class
                if vehicle_profile is not None
                else None
            ),
        },
        "map": {
            "metadata_title_known": map_known,
            "source": "local_metadata" if map_known else None,
        },
        "planned_assets": {
            "vehicle_asset_key": (
                vehicle_profile.vehicle_asset_key
                if vehicle_profile is not None
                else None
            ),
            "vehicle_image_host": (
                urlsplit(vehicle_url).hostname if vehicle_url else None
            ),
            "flag_asset_key": (
                vehicle_profile.flag_asset_key
                if vehicle_profile is not None
                else None
            ),
        },
    }


def serialize_diagnostic_report(report: dict[str, Any]) -> bytes:
    data = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    if len(data) > MAX_REPORT_BYTES:
        raise ValueError("Raport diagnostyczny przekracza limit rozmiaru")
    return data


def save_diagnostic_report(
    path: str | Path,
    report: dict[str, Any],
) -> None:
    data = serialize_diagnostic_report(report)
    Path(path).write_bytes(data)
