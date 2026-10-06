import json
import urllib.request
from typing import Any
from map_catalog import find_map_name
from map_image import read_map_image_hash

API_BASE = "http://127.0.0.1:8111"
ENDPOINTS = (
    "/state",
    "/indicators",
    "/map_info.json",
    "/mission.json",
    "/map_obj.json",
)
MAX_RESPONSE_BYTES = 1_048_576
class ApiResponseError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason

class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    NoRedirectHandler(),
)


def fetch_json(path: str) -> dict[str, Any]:
    if path not in ENDPOINTS:
        raise ValueError("Endpoint nie znajduje się na liście dozwolonych")

    request = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"Accept": "application/json"},
        method="GET",
    )

    with OPENER.open(request, timeout=2) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)

    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("Odpowiedź lokalnego API jest za duża")

    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("Oczekiwano obiektu JSON")

    return data