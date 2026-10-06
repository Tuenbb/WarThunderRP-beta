import json
import os
import sys
import tempfile
from pathlib import Path

APP_NAME = "War Thunder RS"
DISCORD_CLIENT_ID = "1556693607791075358"

DEFAULT_REFRESH_INTERVAL = 3
MIN_REFRESH_INTERVAL = 1
MAX_REFRESH_INTERVAL = 60


def settings_path() -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home()))
    return appdata / "WarThunderRS" / "settings.json"


def load_refresh_interval() -> int:
    path = settings_path()

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return DEFAULT_REFRESH_INTERVAL
    except OSError as error:
        raise OSError("Nie można odczytać ustawień") from error

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("Plik ustawień zawiera nieprawidłowy JSON") from error

    if not isinstance(data, dict):
        raise ValueError("Plik ustawień nie zawiera obiektu JSON")

    interval = data.get("refresh_interval")
    if type(interval) is not int:
        raise ValueError("Brak poprawnego interwału")
    if not MIN_REFRESH_INTERVAL <= interval <= MAX_REFRESH_INTERVAL:
        raise ValueError("Interwał musi być liczbą od 1 do 60")

    return interval


def save_refresh_interval(interval: int) -> None:
    if type(interval) is not int:
        raise ValueError("Interwał musi być liczbą całkowitą")
    if not MIN_REFRESH_INTERVAL <= interval <= MAX_REFRESH_INTERVAL:
        raise ValueError("Interwał musi wynosić od 1 do 60 sekund")

    directory = settings_path().parent
    directory.mkdir(parents=True, exist_ok=True)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=directory,
            prefix="settings-",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump({"refresh_interval": interval}, temp_file)
            temp_file.write("\n")

        os.replace(temp_path, settings_path())
    except OSError:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise


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