import json
import logging
import os
import re
import tempfile
import time
from collections import OrderedDict
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

from vehicle_catalog import get_nation_profile

logger = logging.getLogger(__name__)

WIKI_HOST = "wiki.warthunder.com"
WIKI_UNIT_URL = f"https://{WIKI_HOST}/unit/"
MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_CACHE_BYTES = 1024 * 1024
MAX_CACHE_ENTRIES = 1000
MAX_TRACKED_ATTEMPTS = 256
REQUEST_TIMEOUT_SECONDS = 5
RETRY_DELAY_SECONDS = 300

VEHICLE_ID_PATTERN = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9_-]{0,49}/){0,2}"
    r"[A-Za-z][A-Za-z0-9_-]{0,99}$"
)
WIKI_TITLE_SUFFIX = re.compile(r"\s*\|\s*War Thunder Wiki\s*$", re.IGNORECASE)
COUNTRY_FLAG_FILE = re.compile(r"^country_([a-z0-9_]+)\.svg$", re.IGNORECASE)
_VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)

_last_attempt: OrderedDict[str, float] = OrderedDict()


@dataclass(frozen=True)
class VehicleWikiInfo:
    name: str
    nation_id: str | None = None


@dataclass(frozen=True)
class _CacheEntry:
    name: str
    nation_id: str | None
    nation_checked: bool


class _WikiVehicleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._inside_title = False
        self._title_parts: list[str] = []
        self._stack: list[tuple[str, frozenset[str]]] = []
        self._item_depth: int | None = None
        self._item_parts: list[str] = []
        self._item_country_ids: list[str] = []
        self.title: str | None = None
        self.nation_id: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.casefold()
        attributes = dict(attrs)
        classes = frozenset((attributes.get("class") or "").split())

        if tag == "title":
            self._inside_title = True
        if "game-unit_card-info_item" in classes and self._item_depth is None:
            self._item_depth = len(self._stack) + 1
            self._item_parts = []
            self._item_country_ids = []

        if self._item_depth is not None:
            self._item_parts.append("")
            if tag == "img":
                source = attributes.get("src") or ""
                filename = urlsplit(source).path.rsplit("/", maxsplit=1)[-1]
                country_match = COUNTRY_FLAG_FILE.fullmatch(filename)
                if country_match is not None:
                    self._item_country_ids.append(country_match.group(1))

        if tag not in _VOID_TAGS:
            self._stack.append((tag, classes))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == "title":
            self._inside_title = False

        if (
            self._item_depth is not None
            and len(self._stack) == self._item_depth
            and self._stack[-1][0] == tag
            and "game-unit_card-info_item" in self._stack[-1][1]
        ):
            self._finish_info_item()
            self._item_depth = None
            self._item_parts = []
            self._item_country_ids = []

        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self._title_parts.append(data)
        if self._item_depth is not None:
            self._item_parts.append(data)

    def close(self) -> None:
        super().close()
        title = " ".join("".join(self._title_parts).split())
        title = WIKI_TITLE_SUFFIX.sub("", title).strip()
        if title and len(title) <= 128:
            self.title = title

    def _finish_info_item(self) -> None:
        text = " ".join("".join(self._item_parts).split())
        if re.search(r"\bResearch country\b", text, re.IGNORECASE) is None:
            return

        for country_id in self._item_country_ids:
            nation = get_nation_profile(country_id)
            if nation is not None:
                self.nation_id = nation.nation_id
                return

        country_name = re.split(
            r"\bResearch country\b",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()
        nation = get_nation_profile(country_name)
        if nation is not None:
            self.nation_id = nation.nation_id


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


def _read_cache() -> dict[str, _CacheEntry]:
    path = _cache_path()

    try:
        with path.open("rb") as cache_file:
            raw = cache_file.read(MAX_CACHE_BYTES + 1)
    except FileNotFoundError:
        return {}
    except OSError as error:
        logger.warning("Could not read vehicle-name cache (%s)", type(error).__name__)
        return {}

    if len(raw) > MAX_CACHE_BYTES:
        logger.warning("Vehicle-name cache exceeds the 1 MiB limit")
        return {}

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("Vehicle-name cache is invalid JSON")
        return {}

    if not isinstance(data, dict):
        logger.warning("Vehicle-name cache has an invalid format")
        return {}

    cache: dict[str, _CacheEntry] = {}
    for key, value in list(data.items())[-MAX_CACHE_ENTRIES:]:
        if not isinstance(key, str) or not VEHICLE_ID_PATTERN.fullmatch(key):
            continue

        if isinstance(value, str):
            name = value
            nation_id = None
            nation_checked = False
        elif isinstance(value, dict):
            name = value.get("name")
            nation_value = value.get("nation")
            nation_checked = "nation" in value
            nation = get_nation_profile(nation_value)
            nation_id = nation.nation_id if nation is not None else None
        else:
            continue

        if isinstance(name, str) and 0 < len(name.strip()) <= 128:
            cache[key] = _CacheEntry(
                name=name.strip(),
                nation_id=nation_id,
                nation_checked=nation_checked,
            )
    return cache


def _write_cache(cache: dict[str, _CacheEntry]) -> None:
    path = _cache_path()
    directory = path.parent
    temporary_path: Path | None = None

    serialized = {
        key: (
            {"name": entry.name, "nation": entry.nation_id}
            if entry.nation_checked
            else entry.name
        )
        for key, entry in list(cache.items())[-MAX_CACHE_ENTRIES:]
    }

    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=directory,
            prefix="vehicle-names-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(serialized, temporary_file, ensure_ascii=False, indent=2)
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


def _fetch_wiki_vehicle_info(api_type: str) -> VehicleWikiInfo | None:
    model_id = api_type.rsplit("/", maxsplit=1)[-1]
    url = f"{WIKI_UNIT_URL}{model_id}"
    request = Request(
        url,
        headers={
            "Accept": "text/html",
            "Accept-Language": "en",
            "User-Agent": "WarThunderRS/1.0 (vehicle name and nation lookup)",
        },
        method="GET",
    )

    with _OPENER.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        page = response.read(MAX_PAGE_BYTES + 1)

    if len(page) > MAX_PAGE_BYTES:
        raise ValueError("War Thunder Wiki page exceeds the 2 MiB limit")

    parser = _WikiVehicleParser()
    parser.feed(page.decode("utf-8", errors="replace"))
    parser.close()
    if parser.title is None:
        return None
    return VehicleWikiInfo(parser.title, parser.nation_id)


def _remember_attempt(api_type: str, now: float) -> None:
    _last_attempt[api_type] = now
    _last_attempt.move_to_end(api_type)
    while len(_last_attempt) > MAX_TRACKED_ATTEMPTS:
        _last_attempt.popitem(last=False)


def resolve_vehicle_info(
    api_type: object,
    fallback_name: str,
) -> VehicleWikiInfo:
    if not isinstance(api_type, str) or not VEHICLE_ID_PATTERN.fullmatch(api_type):
        return VehicleWikiInfo(fallback_name)

    cache = _read_cache()
    cached = cache.get(api_type)
    if cached is not None and cached.nation_checked:
        return VehicleWikiInfo(cached.name, cached.nation_id)

    now = time.monotonic()
    last_attempt = _last_attempt.get(api_type)
    if last_attempt is not None and now - last_attempt < RETRY_DELAY_SECONDS:
        return VehicleWikiInfo(
            cached.name if cached is not None else fallback_name,
            cached.nation_id if cached is not None else None,
        )
    _remember_attempt(api_type, now)

    try:
        info = _fetch_wiki_vehicle_info(api_type)
    except (OSError, TimeoutError, URLError, ValueError) as error:
        logger.info(
            "Vehicle Wiki lookup failed for %s (%s)",
            api_type,
            type(error).__name__,
        )
        return VehicleWikiInfo(
            cached.name if cached is not None else fallback_name,
            cached.nation_id if cached is not None else None,
        )

    if info is None:
        logger.info("War Thunder Wiki has no usable title for %s", api_type)
        return VehicleWikiInfo(
            cached.name if cached is not None else fallback_name,
            cached.nation_id if cached is not None else None,
        )

    cache[api_type] = _CacheEntry(
        name=info.name,
        nation_id=info.nation_id,
        nation_checked=True,
    )
    _write_cache(cache)
    return info


def resolve_vehicle_name(api_type: object, fallback_name: str) -> str:
    return resolve_vehicle_info(api_type, fallback_name).name


def get_cached_vehicle_info(api_type: object) -> VehicleWikiInfo | None:
    if not isinstance(api_type, str) or not VEHICLE_ID_PATTERN.fullmatch(api_type):
        return None
    cached = _read_cache().get(api_type)
    if cached is None:
        return None
    return VehicleWikiInfo(cached.name, cached.nation_id)
