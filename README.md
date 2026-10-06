# WarThunderRPC

This worktree includes a beta tester report control and a reproducible Windows
EXE build recipe. See [BETA_TESTING.md](BETA_TESTING.md) for prerequisites,
build/run steps, test scenarios, and the diagnostic report's privacy boundary.

Vehicle names and nations are resolved from the public War Thunder Wiki page at
`https://wiki.warthunder.com/unit/<model-id>`. The app reads the page title and
the vehicle card's **Research country** field; it does not infer a nation from
the vehicle ID or vehicle type. Only recognized country identifiers receive a
flag. If the page or its country field is unavailable, the app keeps the
fallback name and shows no newly inferred flag.

Lookups use HTTPS to `wiki.warthunder.com` only, with a five-second timeout and
a 2 MiB page limit. The local cache is stored at
`%APPDATA%/WarThunderRS/vehicle_names.json` and is limited to 1,000 entries and
1 MiB. Existing name-only cache entries remain readable and are upgraded with
nation data after a successful Wiki lookup. No remote images or page scripts
are fetched by this app. Scripts from Wiki pages are never executed.

Vehicle classes are recognized from known local API `army` values and exact
vehicle category segments (ground, aircraft, helicopters, ships, and boats).
Unknown values are not guessed. Model IDs without a category still get a
readable name and a bounded, ID-derived Wiki image URL; if the API provides no
model ID, the app reports the known class without inventing a vehicle image.
For nations with a local flag image, the Discord small-image key is derived
from the conventional filename (`country_israel` for
`country_israel.png`). The public source release intentionally omits all image
files; Discord requires these keys to be registered in the application's Rich
Presence asset portal. Recognized nations still retain their text flag even
when no local artwork is present.

Battle state can still be identified when `/indicators` reports invalid or
unavailable vehicle data, provided `/map_info.json` is valid and
`/mission.json` contains an active primary objective. In that case the app
shows the battle and map but labels vehicle data unavailable; the current
local API responses do not expose a ship name or class for that situation.

To inspect whether the existing local API offers further map or player-vessel
metadata, run `python probe_battle_metadata.py` during a battle. It reads only
`/map_info.json`, `/mission.json`, and `/map_obj.json`; output is bounded and
redacts dynamic identifiers and unrelated string values. It displays only
`/mission.json`'s bounded `status` and objective `text` values, escaped for
terminal safety, as well as safe endpoint error reasons. `/map_obj.json` is
read as its JSON array response, rather than requiring an object; the probe
summarizes object types and explicit player-related boolean fields across all
records, while keeping record output bounded.

To inspect concise structure and map candidates from the local API, run
`python -B probe_map.py`. It requests only `/state`, `/map_info.json`,
`/map_obj.json`, and `/indicators`, in that order, and continues after
endpoint errors. Object responses show bounded top-level field/type summaries.
The `/map_obj.json` array shows at most three records with bounded field keys
and sample JSON. Every endpoint reports matches for the exact scalar keys
`map_id`, `name`, `map_name`, `location`, `level`, and `zone_id`. Requests use
the guarded localhost client with a two-second timeout, disabled proxies,
blocked redirects, and a one-megabyte response cap.

To inspect the current state and intended Rich Presence image inputs without
connecting to Discord or making Wiki requests, run
`python -B probe_presence.py`. It reads only the existing allowlisted local
game endpoints and the local vehicle-name cache. A vehicle URL host or local
asset filename does not prove that Discord accepts it; image keys must also be
registered in the Discord application's Rich Presence assets. It reports
whether `details` and `state` are actually present in the selected profile
without printing their configured text, whether vehicle/speed template values
are available, the intended large/small image inputs, and the image fallback
order. It does not make a Discord RPC connection or a Wiki request.

Discord rejects an empty `state` field. When the second line is disabled or
resolves empty and at least one image is being sent, the app uses a single
Braille blank (`U+2800`) as the protocol value so the line should remain
visually blank while Discord accepts the non-empty state. With no images, the
`state` field is omitted. Please verify Discord's live rendering with
**Hangar → second line: Wyłączona** in the running app.
If Discord rejects some image candidates but accepts a fallback, the GUI RPC
status reports whether the vehicle image, flag, both, or neither was retained.

Map names from explicit `map_info` or mission map-title fields take priority.
The currently reported `/map_info.json` contains only map grid parameters and
no title; objective text is not treated as a map name. The confirmed
`0000002c7ebdffff` fingerprint is included as a fallback for
`[Dominacja #1] Kvarken Południowy`, not as a replacement for automatic
metadata or a complete map catalog. `/map_obj.json` was unavailable in the
latest object-only probe. The array-capable probe found map/spawn markers but
no explicit player-to-vessel association field.

## Registering map names

The app resolves names in this order: a reliable title from local API metadata,
the user's fingerprint registry, then the checked-in `map_catalog.json`
fallback. Register a confirmed in-game title while that map is active:

```powershell
python register_map.py "[Dominacja #1] Kvarken Południowy"
```

The command reads only the current fingerprint from the local `/map.img` API
and saves the confirmed name to
`%APPDATA%\WarThunderRS\map_names.json`; it does not modify game files or the
checked-in catalog. The registry is updated atomically and limited to 1,000
entries and 256 KiB. Restart or refresh the app after registering if its map
display has not updated yet.

An optional `.bin` directory can be listed to help inspect possible level
identifiers:

```powershell
python register_map.py "Confirmed in-game title" --levels-dir "Z:\path\to\War Thunder\levels"
```

The directory is never guessed or hard-coded; only its `.bin` filenames are
listed, and their stems are explicitly unconfirmed candidates. To store a
level ID annotation, pass `--level-id "candidate_stem"` after checking it
yourself. The annotation does not affect map-name resolution and is not
presented as an API-confirmed identifier. Run the app with `python main.py`.

## Rich Presence customization

Choose **Ustawienia Rich Presence…** in the running app to configure each
state's first and second line. In a custom second line, the app supports
`{vehicle}`, `{speed}`, `{ias}`, `{tas}`, and `{kills}`. Speed/IAS/TAS use the
`/state` values reported by the local game API; `{speed}` prefers IAS and falls
back to TAS. Put a whole optional phrase in square brackets, for example
`[{vehicle} — IAS {ias}]`, so the phrase disappears when one of its values is
unavailable. The current API payloads checked by the app do not expose a
verified match kill-count field, so `{kills}` is blank for now.

To inspect the safe local API fields while flying or in battle, run
`python -B probe_vehicle_state.py`. It reads only `/indicators` and `/state`,
prints the known speed fields, and reports a bounded set of scalar paths whose
names contain `kill`, `frag`, or `score`. It does not print the full response.
An observed candidate still needs confirmation before it can be treated as a
kill count.

Use **Zakończ aplikację** in the main window to stop the poller and tray icon,
clear Discord Rich Presence, and exit. Closing the window itself continues to
minimize the app to the tray.
