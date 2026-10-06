import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk
from typing import Any
from vehicle_catalog import (
    apply_detected_nation,
    get_vehicle_profile,
)
import pystray
from vehicle_names import resolve_vehicle_info
from PIL import Image, ImageDraw

from config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_REFRESH_INTERVAL,
    DISCORD_CLIENT_ID,
    PRESENCE_STATE_KEYS,
    PresenceProfile,
    build_presence_lines,
    default_presence_profiles,
    load_refresh_interval,
    load_presence_profiles,
    save_refresh_interval,
    save_presence_profiles,
    set_startup_enabled,
    startup_enabled,
)
from discord_rpc import DiscordRpcClient
from game_detection import is_game_running
from game_state import (
    classify_presence_state,
    classify_state,
    presence_assets_enabled,
)
from warthunder_api import fetch_json
from map_catalog import find_map_name, find_map_name_from_metadata
from map_image import read_map_image_hash
from presence_stats import extract_presence_values
from diagnostic_report import build_diagnostic_report, save_diagnostic_report


def format_vehicle_id(value: object) -> str | None:
    profile = get_vehicle_profile(value)
    return profile.display_name if profile is not None else None


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
        self.presence_profiles = default_presence_profiles()
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

    def set_presence_profiles(
        self,
        profiles: dict[str, PresenceProfile],
    ) -> None:
        self.presence_profiles = dict(profiles)
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
                state, state_error = try_fetch("/state")
                map_info, map_error = try_fetch("/map_info.json")
                mission, mission_error = try_fetch("/mission.json")

                responses = (indicators, state, map_info, mission)
                available_count = sum(response is not None for response in responses)
                if available_count == len(responses):
                    api_text = "Dostępne"
                elif available_count:
                    api_text = "Częściowo dostępne"
                else:
                    errors = (
                        indicators_error,
                        state_error,
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
                presence_state_key = classify_presence_state(
                    True,
                    indicators,
                    map_info,
                    mission,
                )

                map_text = "—"
                if isinstance(map_info, dict) and map_info.get("valid") is True:
                    map_text = (
                        find_map_name_from_metadata(map_info, mission) or "—"
                    )
                    if map_text == "—":
                        try:
                            fingerprint, _dimensions = read_map_image_hash()
                            map_text = (
                                find_map_name(fingerprint) or "Nieznana mapa"
                            )
                        except (OSError, TimeoutError, ValueError) as error:
                            map_text = (
                                f"Błąd obrazu mapy ({type(error).__name__})"
                            )

                vehicle_text = "—"
                vehicle_name = None
                vehicle_profile = None
                indicators_valid = (
                    isinstance(indicators, dict)
                    and indicators.get("valid") is True
                )
                vehicle_id = (
                    indicators.get("type")
                    if isinstance(indicators, dict)
                    else None
                )

                if indicators_valid:
                    vehicle_profile = get_vehicle_profile(
                        vehicle_id,
                        indicators.get("army"),
                    )
                    if vehicle_profile is not None:
                        wiki_info = (
                            resolve_vehicle_info(
                                vehicle_id,
                                vehicle_profile.display_name,
                            )
                            if vehicle_profile.model_id is not None
                            else None
                        )
                        vehicle_profile = apply_detected_nation(
                            vehicle_profile,
                            wiki_info.nation_id if wiki_info is not None else None,
                        )
                        vehicle_name = (
                            vehicle_profile.display_name
                            if vehicle_profile.vehicle_asset_key is not None
                            else (
                                wiki_info.name
                                if wiki_info is not None
                                else vehicle_profile.display_name
                            )
                        )
                        vehicle_text = vehicle_name
                    else:
                        vehicle_text = "Nieznany pojazd"
                        vehicle_name = vehicle_text
                else:
                    vehicle_text = "Dane pojazdu niedostępne"
                if not self.rpc_enabled:
                    self._rpc.disconnect()
                    rpc_text = "Zatrzymano"
                else:
                    profile = self.presence_profiles.get(
                        presence_state_key or "loading",
                        self.presence_profiles["loading"],
                    )
                    details, second_line = build_presence_lines(
                        profile,
                        vehicle_name,
                        extract_presence_values(state, vehicle_name),
                    )

                    show_vehicle_assets = presence_assets_enabled(
                        presence_state_key
                    )

                    connected = self._rpc.update(
                        DISCORD_CLIENT_ID,
                        second_line,
                        details=details,
                        vehicle_asset_key=(
                            vehicle_profile.vehicle_asset_key
                            if show_vehicle_assets and vehicle_profile is not None
                            else None
                        ),
                        flag_asset_key=(
                            vehicle_profile.flag_asset_key
                            if show_vehicle_assets and vehicle_profile is not None
                            else None
                        ),
                        flag_name=(
                            vehicle_profile.flag_name
                            if show_vehicle_assets and vehicle_profile is not None
                            else None
                        ),
                        vehicle_name=vehicle_name,
                        vehicle_image_url=(
                            vehicle_profile.vehicle_image_url
                            if show_vehicle_assets and vehicle_profile is not None
                            else None
                        ),
                    )
                    rpc_text = "Połączono" if connected else "Rozłączono"
                    if connected and self._rpc.last_update_warning:
                        image_result = {
                            "vehicle+flag": "pojazd + flaga",
                            "vehicle": "pojazd",
                            "flag": "flaga",
                            "none": "brak",
                        }.get(self._rpc.last_image_result or "", "brak")
                        rpc_text = f"Połączono (obrazy: {image_result})"

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
        self.root.title(f"{APP_NAME} beta {APP_VERSION}")
        self.root.minsize(520, 360)
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
            self.presence_profiles = load_presence_profiles()
        except (OSError, ValueError) as error:
            self.presence_profiles = default_presence_profiles()
            messagebox.showwarning(
                "Ustawienia Rich Presence",
                f"Nie można odczytać profili ({type(error).__name__}). "
                "Używam ustawień domyślnych.",
                parent=self.root,
            )
        self.poller.set_presence_profiles(self.presence_profiles)

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

        ttk.Button(
            frame,
            text="Ustawienia Rich Presence…",
            command=self._open_presence_settings,
        ).pack(anchor="w", pady=(10, 0))

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

        ttk.Button(
            frame,
            text="Zakończ aplikację",
            command=self.close,
        ).pack(anchor="e", pady=(8, 0))

        ttk.Button(
            frame,
            text="Zapisz raport diagnostyczny…",
            command=self._save_diagnostic_report,
        ).pack(anchor="e", pady=(6, 0))

        ttk.Label(
            frame,
            text=(
                "Stan jest rozpoznawany heurystycznie z lokalnego API. "
                "Nazwa i nacja pojazdu są pobierane z publicznej Wiki "
                "War Thunder i zapisywane w lokalnym cache."
            ),
            wraplength=460,
        ).pack(anchor="w", pady=(12, 0))

    def _open_presence_settings(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Ustawienia Rich Presence")
        window.transient(self.root)
        window.resizable(True, False)
        window.minsize(620, 420)

        notebook = ttk.Notebook(window, padding=10)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        state_labels = {
            "hangar": "Hangar",
            "loading": "Ładowanie",
            "battle": "Bitwa",
            "test_drive": "Test drive",
        }
        mode_labels = {
            "off": "Wyłączona",
            "custom": "Własny tekst",
            "vehicle": "Nazwa pojazdu (auto)",
        }
        label_modes = {label: mode for mode, label in mode_labels.items()}
        controls: dict[
            str,
            tuple[
                tk.BooleanVar,
                tk.StringVar,
                tk.StringVar,
                tk.StringVar,
                ttk.Entry,
            ],
        ] = {}

        for state_key in PRESENCE_STATE_KEYS:
            profile = self.presence_profiles[state_key]
            tab = ttk.Frame(notebook, padding=18)
            notebook.add(tab, text=state_labels[state_key])

            first_enabled = tk.BooleanVar(value=bool(profile.first_line))
            first_text = tk.StringVar(value=profile.first_line)
            second_mode = tk.StringVar(
                value=mode_labels[profile.second_line_mode]
            )
            second_text = tk.StringVar(value=profile.second_line_text)

            ttk.Label(
                tab,
                text="Pierwsza linia (Discord: Details)",
                font=("Segoe UI", 10, "bold"),
            ).pack(anchor="w")
            first_entry = ttk.Entry(tab, textvariable=first_text)
            first_entry.pack(fill="x", pady=(6, 4))
            ttk.Checkbutton(
                tab,
                text="Wysyłaj pierwszą linię",
                variable=first_enabled,
                command=lambda var=first_enabled, entry=first_entry: entry.configure(
                    state="normal" if var.get() else "disabled"
                ),
            ).pack(anchor="w")
            if not profile.first_line:
                first_entry.configure(state="disabled")

            ttk.Label(
                tab,
                text="Druga linia (Discord: State)",
                font=("Segoe UI", 10, "bold"),
            ).pack(anchor="w", pady=(18, 0))
            mode_box = ttk.Combobox(
                tab,
                textvariable=second_mode,
                values=tuple(mode_labels.values()),
                state="readonly",
            )
            mode_box.pack(fill="x", pady=(6, 4))
            ttk.Label(
                tab,
                text="Własny tekst (używany tylko przy opcji „Własny tekst”)",
            ).pack(anchor="w", pady=(8, 0))
            second_entry = ttk.Entry(tab, textvariable=second_text)
            second_entry.pack(fill="x", pady=(4, 0))
            ttk.Label(
                tab,
                text=(
                    "Pola: {vehicle}, {speed}, {ias}, {tas}, {kills}. "
                    "Użyj nawiasów kwadratowych dla opcjonalnego fragmentu, "
                    "np. [IAS {ias}], który znika, gdy wartość jest niedostępna. "
                    "{kills} pozostaje puste, dopóki API nie udostępni "
                    "potwierdzonego pola liczby zniszczeń."
                ),
                wraplength=540,
            ).pack(anchor="w", pady=(6, 0))

            def update_second_entry(
                _event: object | None = None,
                mode_var: tk.StringVar = second_mode,
                entry: ttk.Entry = second_entry,
            ) -> None:
                entry.configure(
                    state=(
                        "normal"
                        if label_modes.get(mode_var.get()) == "custom"
                        else "disabled"
                    )
                )

            mode_box.bind("<<ComboboxSelected>>", update_second_entry)
            update_second_entry()
            controls[state_key] = (
                first_enabled,
                first_text,
                second_mode,
                second_text,
                first_entry,
            )

        buttons = ttk.Frame(window, padding=(12, 0, 12, 12))
        buttons.pack(fill="x")

        def save_profiles() -> None:
            profiles: dict[str, PresenceProfile] = {}
            for state_key, (
                first_enabled,
                first_text,
                second_mode,
                second_text,
                _first_entry,
            ) in controls.items():
                mode = label_modes.get(second_mode.get())
                if mode is None:
                    messagebox.showerror(
                        "Nieprawidłowe ustawienie",
                        "Wybierz dostępny tryb drugiej linii.",
                        parent=window,
                    )
                    return
                profiles[state_key] = PresenceProfile(
                    first_text.get() if first_enabled.get() else "",
                    mode,
                    second_text.get(),
                )
            try:
                save_presence_profiles(profiles)
            except (OSError, ValueError) as error:
                messagebox.showerror(
                    "Błąd zapisu",
                    f"Nie można zapisać profili ({type(error).__name__}).",
                    parent=window,
                )
                return

            self.presence_profiles = profiles
            self.poller.set_presence_profiles(profiles)
            window.destroy()

        ttk.Button(
            buttons,
            text="Anuluj",
            command=window.destroy,
        ).pack(side="right")
        ttk.Button(
            buttons,
            text="Zapisz profile",
            command=save_profiles,
        ).pack(side="right", padx=(0, 8))

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

    def _save_diagnostic_report(self) -> None:
        consent = messagebox.askyesno(
            "Raport diagnostyczny — beta",
            "Po wybraniu miejsca zapisania raport odczyta wyłącznie "
            "lokalne endpointy War Thunder z istniejącej listy dozwolonych. "
            "Plik zawiera czas UTC, wersję aplikacji/Pythona/Windows, "
            "wykrycie uruchomienia gry, dostępność endpointów i typy błędów, "
            "rozpoznany stan, tylko informację czy pojazd/mapa są znane oraz "
            "klasę pojazdu, planowane klucze assetów i host URL obrazu.\n\n"
            "Nie zapisuje nazw pojazdów/map, identyfikatorów, treści "
            "obecności, cache, pełnych odpowiedzi API, ścieżek ani "
            "poświadczeń. Raport nie jest wysyłany automatycznie.\n\n"
            "Czy chcesz kontynuować?",
            parent=self.root,
        )
        if not consent:
            return

        report_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Zapisz raport diagnostyczny",
            defaultextension=".json",
            initialfile="WarThunderRPC-diagnostic.json",
            filetypes=(("Raport JSON", "*.json"), ("Wszystkie pliki", "*.*")),
        )
        if not report_path:
            return

        try:
            report = build_diagnostic_report()
            save_diagnostic_report(report_path, report)
        except (OSError, ValueError) as error:
            messagebox.showerror(
                "Nie udało się zapisać raportu",
                f"Raport nie został zapisany ({type(error).__name__}).",
                parent=self.root,
            )
            return

        messagebox.showinfo(
            "Raport zapisany",
            "Raport diagnostyczny zapisano lokalnie. Sprawdź jego zawartość "
            "i dołącz go ręcznie tylko wtedy, gdy chcesz go udostępnić.",
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
        try:
            if self.tray_icon is not None:
                self.tray_icon.stop()
        finally:
            self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    WarThunderRpcApp().run()