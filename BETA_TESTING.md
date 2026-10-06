# WarThunderRPC beta testing

## Prerequisites

- Windows 10 or 11.
- War Thunder running with its local game HTTP API available at
  `http://127.0.0.1:8111`.
- Discord desktop running and Rich Presence enabled.
- For an EXE build, Python 3.13 and the packages in `requirements-build.txt`.

The beta only polls the application's existing loopback API allowlist. The
diagnostic report is opt-in, saved locally via a Save As dialog, and never
uploaded automatically.

## Build the Windows executable

From the repository directory in PowerShell:

```powershell
py -3.13 -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv-build\Scripts\python.exe -m PyInstaller --clean --noconfirm WarThunderRPC.spec
```

The windowed one-file executable is created at `dist\WarThunderRPC.exe`.
The spec bundles `map_catalog.json`, Tkinter and the dynamic
`pystray`/`pypresence` imports. It intentionally excludes game-derived image
files; vehicle images use the existing public image URL behavior and Discord
flags use registered portal assets. Builds should be made and tested on
Windows; this project does not include a built executable.

## Launch

1. Start Discord desktop and sign in.
2. Start War Thunder and wait until its local API is available.
3. Run `dist\WarThunderRPC.exe` (or `python main.py` from a source checkout).
4. Keep the app window open for status inspection. Closing the window minimizes
   it to the tray; use **Zakończ aplikację** to fully exit.
5. Rich Presence text is configurable under **Ustawienia Rich Presence…**.

## Test cases

Record the observed state, vehicle/map-known indicators, and Discord result for
each case. Do not include account names or player identifiers in screenshots.

| Scenario | Expected application behavior |
| --- | --- |
| Hangar with a known vehicle | State remains Hangar; resolved vehicle and available nation assets may display. |
| Loading into a match | Loading text; no vehicle/map assets until gameplay data is ready. |
| Ground battle | Battle state when an active primary objective is present; vehicle and nation assets when supplied by local data/cache. |
| Aircraft battle | Battle state and supported IAS/TAS template fields from `/state`. |
| Test Drive | Test Drive state; vehicle name/assets where the API, cache, and Discord assets support them. |
| Naval battle with invalid vehicle indicators | Battle/map may be recognized from mission/map data; vehicle remains unavailable rather than guessed. |
| Custom Rich Presence lines | Off/custom/vehicle and `{vehicle}`, `{speed}`, `{ias}`, `{tas}`, `{kills}` substitutions behave as configured. |
| Quit button | Polling stops, Discord presence clears, tray icon stops, and the app exits. |
| Diagnostic report | Save dialog writes a redacted JSON report only after consent; cancelling either prompt writes nothing. |

## Diagnostic report and privacy

Use **Zapisz raport diagnostyczny…** to review a notice and choose a local
destination. The report contains only:

- App, Python, and Windows version information and report timestamp.
- Local game-process detection result and reachability/error class for the
  existing API endpoints.
- Recognized state key; a boolean for whether a vehicle model/class is
  available; whether local API metadata contains a map title; vehicle class
  only.
- Planned Discord asset-key names and the public vehicle-image hostname.

It does not include usernames, home/install paths, vehicle/map names or raw
IDs, Discord application credentials/tokens, custom Presence text, cache
contents, full API payloads, or exception messages. No report is transmitted
by the app. Review the saved file and attach it manually only if you choose to
share it. Reports should be treated as user-provided diagnostics.

The public source repository and EXE bundle omit the local `assets/` image
directory. Discord image rendering therefore requires the corresponding
vehicle/flag assets to be registered in the configured Discord application's
Rich Presence asset portal; text state and detection continue to work without
redistributed image files.

## Reporting a result

When reporting a test, include the scenario, whether the visible Discord
activity matched expectations, and any app status/error class. If useful,
attach the saved JSON report manually after reviewing it. Do not include
credentials, account identifiers, or unredacted game/API dumps.
