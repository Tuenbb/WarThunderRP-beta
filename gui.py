import queue
import re
import threading
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import Any
from vehicle_catalog import get_vehicle_profile
import pystray
from vehicle_names import resolve_vehicle_name
from PIL import Image, ImageDraw

from config import (
    APP_NAME,
    DEFAULT_REFRESH_INTERVAL,
    DISCORD_CLIENT_ID,
    load_refresh_interval,
    save_refresh_interval,
    set_startup_enabled,
    startup_enabled,
)
from discord_rpc import DiscordRpcClient
from game_detection import is_game_running
from game_state import classify_state
from warthunder_api import fetch_json
from map_catalog import find_map_name
from map_image import read_map_image_hash

VEHICLE_ID_PATTERN = re.compile(
    r"^[A-Za-z][A-Za-z0-9_-]{0,39}/[A-Za-z0-9_-]{1,100}$"
)

VEHICLE_NATION_FLAGS = {
    "ussr": "🇷🇺",
    "sov": "🇷🇺",
    "germ": "🇩🇪",
    "usa": "🇺🇸",
    "uk": "🇬🇧",
    "fr": "🇫🇷",
    "it": "🇮🇹",
    "jp": "🇯🇵",
    "china": "🇨🇳",
    "cn": "🇨🇳",
    "sweden": "🇸🇪",
    "sw": "🇸🇪",
    "isr": "🇮🇱",
    "israel": "🇮🇱",
    "pol": "🇵🇱",
    "czech": "🇨🇿",
    "cz": "🇨🇿",
    "hungary": "🇭🇺",
    "hu": "🇭🇺",
    "austria": "🇦🇹",
    "aus": "🇦🇹",
}


def format_vehicle_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    identifier = value.strip()
    if not VEHICLE_ID_PATTERN.fullmatch(identifier):
        return None

    model_id = identifier.rsplit("/", 1)[1]
    display_name = model_id.replace("_", " ").title()

    flag = next(
        (
            emoji
            for prefix, emoji in VEHICLE_NATION_FLAGS.items()
            if model_id.casefold().startswith(prefix)
        ),
        None,
    )
    return f"{flag} {display_name}" if flag else display_name


def try_fetch(endpoint: str) -> tuple[Any | None, str | None]:
    try:
        return fetch_json(endpoint), None
    except (OSError, TimeoutError, ValueError) as error:
        return None, type(error).__name__


@dataclass(frozen=True)
class StatusUpdate:
    game: str
    activity: str
    api: str
    map_name: str
    vehicle: str
    rpc: str


class StatusPoller(threading.Thread):
    def __init__(self, interval_seconds: int) -> None:
        super().__init__(name="WarThunderStatusPoller", daemon=True)
        self.interval_seconds = interval_seconds
        self.rpc_enabled = True
        self.results: queue.Queue[StatusUpdate] = queue.Queue()
        self._stop_event = threading.Event()
        self._refresh_event = threading.Event()
        self._rpc = DiscordRpcClient()

    def request_refresh(self) -> None:
        self._refresh_event.set()

    def set_rpc_enabled(self, enabled: bool) -> None:
        self.rpc_enabled = enabled
        self._refresh_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._refresh_event.set()

    def run(self) -> None:
        try:
            while not self._stop_event.is_set():
                self._refresh_event.wait(timeout=self.interval_seconds)
                self._refresh_event.clear()

                if self._stop_event.is_set():
                    break

                if not self.rpc_enabled:
                    self._rpc.disconnect()

                try:
                    game_running = is_game_running()
                except OSError as error:
                    self._rpc.disconnect()
                    rpc_text = "Zatrzymano" if not self.rpc_enabled else "Rozłączono"
                    self.results.put(
                        StatusUpdate(
                            "Błąd wykrywania",
                            "—",
                            type(error).__name__,
                            "—",
                            "—",
                            rpc_text,
                        )
                    )
                    continue

                if not game_running:
                    self._rpc.disconnect()
                    rpc_text = "Zatrzymano" if not self.rpc_enabled else "Rozłączono"
                    self.results.put(
                        StatusUpdate(
                            "Niewykryty",
                            "—",
                            "—",
                            "—",
                            "—",
                            rpc_text,
                        )
                    )
                    continue

                indicators, indicators_error = try_fetch("/indicators")
                map_info, map_error = try_fetch("/map_info.json")
                mission, mission_error = try_fetch("/mission.json")

                responses = (indicators, map_info, mission)
                available_count = sum(response is not None for response in responses)
                if available_count == len(responses):
                    api_text = "Dostępne"
                elif available_count:
                    api_text = "Częściowo dostępne"
                else:
                    errors = (
                        indicators_error,
                        map_error,
                        mission_error,
                    )
                    first_error = next(
                        (error for error in errors if error is not None),
                        "błąd",
                    )
                    api_text = f"Niedostępne ({first_error})"

                activity_text = classify_state(
                    True,
                    indicators,
                    map_info,
                    mission,
                )

                map_text = "—"
                if isinstance(map_info, dict) and map_info.get("valid") is True:
                    try:
                        fingerprint, _dimensions = read_map_image_hash()
                        map_text = find_map_name(fingerprint) or "Nieznana mapa"
                    except (OSError, TimeoutError, ValueError) as error:
                        map_text = f"Błąd obrazu mapy ({type(error).__name__})"

                vehicle_text = "—"
                vehicle_profile = None
                vehicle_id = (
                    indicators.get("type")
                    if isinstance(indicators, dict)
                    else None
                )

                if (
                    isinstance(indicators, dict)
                    and indicators.get("valid") is True
                ):
                    vehicle_profile = get_vehicle_profile(vehicle_id)
                    if vehicle_profile is not None:
                        vehicle_text = vehicle_profile.display_name
                        if vehicle_profile.vehicle_asset_key is None:
                            vehicle_text = resolve_vehicle_name(
                                vehicle_id,
                                vehicle_profile.display_name,
                            )
                    else:
                        vehicle_text = format_vehicle_id(vehicle_id) or "—"
                if not self.rpc_enabled:
                    self._rpc.disconnect()
                    rpc_text = "Zatrzymano"
                else:
                    presence_parts = [activity_text]
                    if map_text not in ("—", "Nieznana mapa") and not map_text.startswith("Błąd"):
                        presence_parts.append(map_text)
                    if vehicle_text != "—":
                        presence_parts.append(vehicle_text)

                    presence_state = " / ".join(presence_parts)

                    connected = self._rpc.update(
                        DISCORD_CLIENT_ID,
                        presence_state,
                        vehicle_asset_key=(
                            vehicle_profile.vehicle_asset_key
                            if vehicle_profile is not None
                            else None
                        ),
                        flag_asset_key=(
                            vehicle_profile.flag_asset_key
                            if vehicle_profile is not None
                            else None
                        ),
                        flag_name=(
                            vehicle_profile.flag_name
                            if vehicle_profile is not None
                            else None
                        ),
                        vehicle_name=(
                            vehicle_text
                            if vehicle_text != "—"
                            else None
                        ),
                        vehicle_image_url=(
                            vehicle_profile.vehicle_image_url
                            if vehicle_profile is not None
                            else None
                        ),
                    )
                    rpc_text = "Połączono" if connected else "Rozłączono"

                self.results.put(
                    StatusUpdate(
                        "Wykryty",
                        activity_text,
                        api_text,
                        map_text,
                        vehicle_text,
                        rpc_text,
                    )
                )
        finally:
            self._rpc.disconnect()


class WarThunderRpcApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.minsize(500, 320)
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        try:
            interval = load_refresh_interval()
        except (OSError, ValueError) as error:
            interval = DEFAULT_REFRESH_INTERVAL
            messagebox.showwarning(
                "Ustawienia",
                f"Nie można odczytać interwału ({type(error).__name__}). "
                f"Używam {DEFAULT_REFRESH_INTERVAL} sekund.",
                parent=self.root,
            )

        self.poller = StatusPoller(interval)
        self.tray_icon: Any | None = None
        self._closing = False

        self.game_status = tk.StringVar(value="Sprawdzanie…")
        self.activity_status = tk.StringVar(value="—")
        self.api_status = tk.StringVar(value="—")
        self.map_status = tk.StringVar(value="—")
        self.vehicle_status = tk.StringVar(value="—")
        self.rpc_status = tk.StringVar(value="Rozłączono")
        self.interval = tk.StringVar(value=str(interval))

        try:
            startup_value = startup_enabled()
        except OSError:
            startup_value = False
        self.startup_enabled = tk.BooleanVar(value=startup_value)

        self._build_ui()
        self.poller.start()
        self.poller.request_refresh()
        self.root.after(200, self._read_results)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=APP_NAME,
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        self._row(frame, "War Thunder:", self.game_status)
        self._row(frame, "Aktywność:", self.activity_status)
        self._row(frame, "Mapa:", self.map_status)
        self._row(frame, "Lokalne API:", self.api_status)
        self._row(frame, "Discord Rich Presence:", self.rpc_status)
        self._row(frame, "Pojazd (ID API):", self.vehicle_status)

        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=(16, 0))

        ttk.Label(
            controls,
            text="Interwał (sekundy, 1–60):",
        ).pack(side="left")

        ttk.Spinbox(
            controls,
            from_=1,
            to=60,
            width=5,
            textvariable=self.interval,
        ).pack(side="left", padx=6)

        ttk.Button(
            controls,
            text="Zastosuj",
            command=self._apply_interval,
        ).pack(side="left")

        ttk.Button(
            controls,
            text="Odśwież teraz",
            command=self.poller.request_refresh,
        ).pack(side="right")

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(12, 0))

        self.rpc_button = ttk.Button(
            buttons,
            text="Zatrzymaj RPC",
            command=self._toggle_rpc,
        )
        self.rpc_button.pack(side="left")

        ttk.Checkbutton(
            buttons,
            text="Uruchom przy starcie Windows",
            variable=self.startup_enabled,
            command=self._toggle_startup,
        ).pack(side="left", padx=(12, 0))

        ttk.Button(
            buttons,
            text="Minimalizuj do traya",
            command=self.minimize_to_tray,
        ).pack(side="right")

        ttk.Label(
            frame,
            text=(
                "Stan jest rozpoznawany heurystycznie z lokalnego API. "
                "Nazwa pojazdu pochodzi z identyfikatora API."
            ),
            wraplength=460,
        ).pack(anchor="w", pady=(12, 0))

    @staticmethod
    def _row(
        parent: tk.Misc,
        label: str,
        value: tk.StringVar,
    ) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=26).pack(side="left")
        ttk.Label(row, textvariable=value).pack(side="left")

    def _apply_interval(self) -> None:
        try:
            interval = int(self.interval.get())
        except ValueError:
            interval = 0

        if not 1 <= interval <= 60:
            messagebox.showerror(
                "Nieprawidłowy interwał",
                "Wpisz liczbę całkowitą od 1 do 60.",
                parent=self.root,
            )
            self.interval.set(str(self.poller.interval_seconds))
            return

        try:
            save_refresh_interval(interval)
        except (OSError, ValueError) as error:
            messagebox.showerror(
                "Błąd zapisu",
                f"Nie można zapisać ustawienia ({type(error).__name__}).",
                parent=self.root,
            )
            self.interval.set(str(self.poller.interval_seconds))
            return

        self.poller.interval_seconds = interval
        self.poller.request_refresh()

    def _toggle_rpc(self) -> None:
        enabled = not self.poller.rpc_enabled
        self.poller.set_rpc_enabled(enabled)
        self.rpc_button.configure(
            text="Zatrzymaj RPC" if enabled else "Uruchom RPC"
        )

    def _toggle_startup(self) -> None:
        try:
            set_startup_enabled(self.startup_enabled.get())
        except OSError as error:
            self.startup_enabled.set(not self.startup_enabled.get())
            messagebox.showerror(
                "Błąd autostartu",
                f"Nie można zmienić autostartu ({type(error).__name__}).",
                parent=self.root,
            )

    def _read_results(self) -> None:
        if self._closing:
            return

        latest = None
        while True:
            try:
                latest = self.poller.results.get_nowait()
            except queue.Empty:
                break

        if latest is not None:
            self.game_status.set(latest.game)
            self.activity_status.set(latest.activity)
            self.api_status.set(latest.api)
            self.map_status.set(latest.map_name)
            self.vehicle_status.set(latest.vehicle)
            self.rpc_status.set(latest.rpc)

        self.root.after(200, self._read_results)

    def minimize_to_tray(self) -> None:
        self._ensure_tray_icon()
        self.root.withdraw()

    def _ensure_tray_icon(self) -> None:
        if self.tray_icon is not None:
            return

        image = Image.new("RGB", (64, 64), "#1f6feb")
        draw = ImageDraw.Draw(image)
        draw.text((14, 22), "RS", fill="white")

        menu = pystray.Menu(
            pystray.MenuItem(
                "Pokaż",
                lambda _icon, _item: self.root.after(0, self.show_window),
            ),
            pystray.MenuItem(
                "Zakończ",
                lambda _icon, _item: self.root.after(0, self.close),
            ),
        )

        icon = pystray.Icon(
            "WarThunderRS",
            image,
            APP_NAME,
            menu,
        )
        self.tray_icon = icon

        threading.Thread(
            target=icon.run,
            name="WarThunderTray",
            daemon=True,
        ).start()

    def show_window(self) -> None:
        if self._closing:
            return
        self.root.deiconify()
        self.root.lift()

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.poller.stop()
        if self.tray_icon is not None:
            self.tray_icon.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    WarThunderRpcApp().run()