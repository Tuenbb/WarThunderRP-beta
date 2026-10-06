import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

APP_NAME = "War Thunder RS"
APP_VERSION = "0.2.0-beta.1"
DISCORD_CLIENT_ID = "1556693607791075358"

DEFAULT_REFRESH_INTERVAL = 3
MIN_REFRESH_INTERVAL = 1
MAX_REFRESH_INTERVAL = 60
MAX_SETTINGS_BYTES = 256 * 1024
MAX_PRESENCE_TEXT_LENGTH = 128
PRESENCE_STATE_KEYS = ("hangar", "loading", "battle", "test_drive")
PRESENCE_LINE_MODES = ("off", "custom", "vehicle")
_PRESENCE_DEFAULTS = {
    "hangar": ("W hangarze", "off", ""),
    "loading": ("Ładowanie…", "off", ""),
    "battle": ("W bitwie", "vehicle", ""),
    "test_drive": ("Jazda próbna", "vehicle", ""),
}
_PRESENCE_TEXT_PATTERN = re.compile(r"^[^\x00-\x1f\x7f]*$")
_PRESENCE_PLACEHOLDER_PATTERN = re.compile(r"\{([a-z_]+)\}")
_PRESENCE_OPTIONAL_SEGMENT_PATTERN = re.compile(r"\[([^\[\]]*)\]")
_PRESENCE_PLACEHOLDERS = frozenset(
    {"vehicle", "speed", "ias", "tas", "kills"}
)


@dataclass(frozen=True)
class PresenceProfile:
    first_line: str
    second_line_mode: str
    second_line_text: str


def default_presence_profiles() -> dict[str, PresenceProfile]:
    return {
        key: PresenceProfile(*_PRESENCE_DEFAULTS[key])
        for key in PRESENCE_STATE_KEYS
    }


def build_presence_lines(
    profile: PresenceProfile,
    vehicle_name: str | None,
    values: Mapping[str, str | None] | None = None,
) -> tuple[str | None, str | None]:
    details = profile.first_line or None
    if profile.second_line_mode == "custom":
        replacements: dict[str, str | None] = {
            "vehicle": vehicle_name,
            "speed": None,
            "ias": None,
            "tas": None,
            "kills": None,
        }
        if values is not None:
            replacements.update(
                {
                    key: value
                    for key, value in values.items()
                    if key in _PRESENCE_PLACEHOLDERS
                }
            )
        state = _render_presence_template(
            profile.second_line_text,
            replacements,
        )
    elif profile.second_line_mode == "vehicle":
        state = vehicle_name or None
    else:
        state = None
    return details, state


def _render_presence_template(
    template: str,
    values: Mapping[str, str | None],
) -> str | None:
    def render_optional(match: re.Match[str]) -> str:
        segment = match.group(1)
        placeholders = _PRESENCE_PLACEHOLDER_PATTERN.findall(segment)
        if not placeholders or any(
            name not in _PRESENCE_PLACEHOLDERS or not values.get(name)
            for name in placeholders
        ):
            return ""
        return segment

    rendered = _PRESENCE_OPTIONAL_SEGMENT_PATTERN.sub(
        render_optional,
        template,
    )
    rendered = _PRESENCE_PLACEHOLDER_PATTERN.sub(
        lambda match: (
            values.get(match.group(1)) or ""
            if match.group(1) in _PRESENCE_PLACEHOLDERS
            else ""
        ),
        rendered,
    )
    rendered = re.sub(r"\s+", " ", rendered)
    rendered = re.sub(r"\s+([,;:!?])", r"\1", rendered).strip()
    rendered = rendered.strip(" ,;:!?|-/")
    return rendered or None


def settings_path() -> Path:
    appdata = Path(os.environ.get("APPDATA") or Path.home())
    return appdata / "WarThunderRS" / "settings.json"


def _read_settings() -> dict[str, object]:
    path = settings_path()

    try:
        with path.open("rb") as settings_file:
            raw = settings_file.read(MAX_SETTINGS_BYTES + 1)
    except FileNotFoundError:
        return {}
    except OSError as error:
        raise OSError("Nie można odczytać ustawień") from error

    if len(raw) > MAX_SETTINGS_BYTES:
        raise ValueError("Plik ustawień przekracza limit rozmiaru")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Plik ustawień zawiera nieprawidłowy JSON") from error

    if not isinstance(data, dict):
        raise ValueError("Plik ustawień nie zawiera obiektu JSON")
    return data


def _validate_refresh_interval(value: object) -> int:
    interval = value
    if type(interval) is not int:
        raise ValueError("Brak poprawnego interwału")
    if not MIN_REFRESH_INTERVAL <= interval <= MAX_REFRESH_INTERVAL:
        raise ValueError("Interwał musi być liczbą od 1 do 60")
    return interval


def load_refresh_interval() -> int:
    data = _read_settings()
    if "refresh_interval" not in data:
        return DEFAULT_REFRESH_INTERVAL
    return _validate_refresh_interval(data["refresh_interval"])


def _validate_presence_profile(
    value: object,
    state_key: str,
) -> PresenceProfile:
    if not isinstance(value, dict):
        raise ValueError(f"Nieprawidłowy profil Rich Presence: {state_key}")

    first_line = value.get("first_line", _PRESENCE_DEFAULTS[state_key][0])
    second_line_mode = value.get(
        "second_line_mode",
        _PRESENCE_DEFAULTS[state_key][1],
    )
    second_line_text = value.get(
        "second_line_text",
        _PRESENCE_DEFAULTS[state_key][2],
    )
    for line in (first_line, second_line_text):
        if (
            not isinstance(line, str)
            or len(line) > MAX_PRESENCE_TEXT_LENGTH
            or not _PRESENCE_TEXT_PATTERN.fullmatch(line)
        ):
            raise ValueError(f"Nieprawidłowy tekst Rich Presence: {state_key}")
    if second_line_mode not in PRESENCE_LINE_MODES:
        raise ValueError(f"Nieprawidłowy tryb drugiej linii: {state_key}")

    return PresenceProfile(first_line, second_line_mode, second_line_text)


def load_presence_profiles() -> dict[str, PresenceProfile]:
    data = _read_settings()
    raw_profiles = data.get("presence")
    if raw_profiles is None:
        return default_presence_profiles()
    if not isinstance(raw_profiles, dict):
        raise ValueError("Ustawienia Rich Presence muszą być obiektem")

    defaults = default_presence_profiles()
    profiles: dict[str, PresenceProfile] = {}
    for state_key in PRESENCE_STATE_KEYS:
        raw_profile = raw_profiles.get(state_key)
        if raw_profile is None:
            profiles[state_key] = defaults[state_key]
        else:
            profiles[state_key] = _validate_presence_profile(
                raw_profile,
                state_key,
            )
    if set(raw_profiles) - set(PRESENCE_STATE_KEYS):
        raise ValueError("Ustawienia Rich Presence zawierają nieznany stan")
    return profiles


def _write_settings(data: dict[str, object]) -> None:
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    encoded = serialized.encode("utf-8")
    if len(encoded) > MAX_SETTINGS_BYTES:
        raise ValueError("Zapis ustawień przekroczył limit rozmiaru")

    directory = settings_path().parent
    directory.mkdir(parents=True, exist_ok=True)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=directory,
            prefix="settings-",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(encoded)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, settings_path())
    except OSError:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise


def save_refresh_interval(interval: int) -> None:
    _validate_refresh_interval(interval)
    data = _read_settings()
    data["refresh_interval"] = interval
    _write_settings(data)


def save_presence_profiles(
    profiles: Mapping[str, PresenceProfile],
) -> None:
    if set(profiles) != set(PRESENCE_STATE_KEYS):
        raise ValueError("Wymagane są profile wszystkich czterech stanów")

    validated = {
        state_key: _validate_presence_profile(
            {
                "first_line": profile.first_line,
                "second_line_mode": profile.second_line_mode,
                "second_line_text": profile.second_line_text,
            },
            state_key,
        )
        for state_key, profile in profiles.items()
    }
    data = _read_settings()
    data["presence"] = {
        state_key: {
            "first_line": profile.first_line,
            "second_line_mode": profile.second_line_mode,
            "second_line_text": profile.second_line_text,
        }
        for state_key, profile in validated.items()
    }
    _write_settings(data)


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'

    project_dir = Path(__file__).resolve().parent
    return f'"{Path(sys.executable).resolve()}" "{project_dir / "main.py"}"'


def startup_enabled() -> bool:
    if os.name != "nt":
        return False

    import winreg

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, "WarThunderRS")
            return value == startup_command()
    except FileNotFoundError:
        return False


def set_startup_enabled(enabled: bool) -> None:
    if os.name != "nt":
        raise OSError("Autostart działa tylko pod Windows")

    import winreg

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    if enabled:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            key_path,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, "WarThunderRS", 0, winreg.REG_SZ, startup_command())
        return

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            key_path,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, "WarThunderRS")
    except FileNotFoundError:
        pass