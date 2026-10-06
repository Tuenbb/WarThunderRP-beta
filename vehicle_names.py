import json
import logging
import os
import re
import tempfile
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

logger = logging.getLogger(__name__)

WIKI_HOST = "wiki.warthunder.com"
WIKI_UNIT_URL = f"https://{WIKI_HOST}/unit/"
MAX_PAGE_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 5
RETRY_DELAY_SECONDS = 300

VEHICLE_ID_PATTERN = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9_-]{0,49}/)?[A-Za-z][A-Za-z0-9_-]{0,99}$"
)
WIKI_TITLE_SUFFIX = re.compile(r"\s*\|\s*War Thunder Wiki\s*$", re.IGNORECASE)

_last_attempt: dict[str, float] = {}


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._inside_title = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "title":
            self._inside_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "title":
            self._inside_title = False

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self.parts.append(data)


class _WikiRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        destination = urlsplit(newurl)
        if destination.scheme != "https" or destination.hostname != WIKI_HOST:
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = build_opener(_WikiRedirectHandler())


def _cache_path() -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home()))
    return appdata / "WarThunderRS" / "vehicle_names.json"


def _read_cache() -> dict[str, str]:
    path = _cache_path()

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as error:
        logger.warning("Could not read vehicle-name cache (%s)", type(error).__name__)
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Vehicle-name cache is invalid JSON")
        return {}

    if not isinstance(data, dict):
        logger.warning("Vehicle-name cache has an invalid format")
        return {}

    return {
        key: name
        for key, name in data.items()
        if isinstance(key, str)
        and VEHICLE_ID_PATTERN.fullmatch(key)
        and isinstance(name, str)
        and 0 < len(name.strip()) <= 128
    }


def _write_cache(cache: dict[str, str]) -> None:
    path = _cache_path()
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=directory,
            prefix="vehicle-names-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(cache, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")

        os.replace(temporary_path, path)
    except OSError as error:
        logger.warning(
            "Could not save vehicle-name cache (%s)",
            type(error).__name__,
        )
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove temporary name-cache file")


def _fetch_wiki_title(api_type: str) -> str | None:
    model_id = api_type.rsplit("/", maxsplit=1)[-1]
    url = f"{WIKI_UNIT_URL}{model_id}"
    request = Request(
        url,
        headers={
            "Accept": "text/html",
            "User-Agent": "WarThunderRS/1.0 (vehicle-name lookup)",
        },
        method="GET",
    )

    with _OPENER.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        page = response.read(MAX_PAGE_BYTES + 1)

    if len(page) > MAX_PAGE_BYTES:
        raise ValueError("War Thunder Wiki page exceeds the 2 MiB limit")

    parser = _TitleParser()
    parser.feed(page.decode("utf-8", errors="replace"))
    title = " ".join("".join(parser.parts).split())
    title = WIKI_TITLE_SUFFIX.sub("", title).strip()

    if not title or len(title) > 128:
        return None
    return title


def resolve_vehicle_name(api_type: object, fallback_name: str) -> str:
    if not isinstance(api_type, str) or not VEHICLE_ID_PATTERN.fullmatch(api_type):
        return fallback_name

    cache = _read_cache()
    cached_name = cache.get(api_type)
    if cached_name:
        return cached_name

    now = time.monotonic()
    last_attempt = _last_attempt.get(api_type)
    if last_attempt is not None and now - last_attempt < RETRY_DELAY_SECONDS:
        return fallback_name
    _last_attempt[api_type] = now

    try:
        name = _fetch_wiki_title(api_type)
    except (OSError, TimeoutError, URLError, ValueError) as error:
        logger.info(
            "Vehicle-name lookup failed for %s (%s)",
            api_type,
            type(error).__name__,
        )
        return fallback_name

    if name is None:
        logger.info("War Thunder Wiki has no usable title for %s", api_type)
        return fallback_name

    cache[api_type] = name
    _write_cache(cache)
    return name