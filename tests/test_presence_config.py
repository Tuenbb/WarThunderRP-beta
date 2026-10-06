import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import (
    DEFAULT_REFRESH_INTERVAL,
    PRESENCE_STATE_KEYS,
    PresenceProfile,
    build_presence_lines,
    default_presence_profiles,
    load_presence_profiles,
    load_refresh_interval,
    save_presence_profiles,
    save_refresh_interval,
)


class PresenceSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "WarThunderRS" / "settings.json"
        self.path_patch = patch("config.settings_path", return_value=self.path)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)

    def test_defaults_cover_all_states_and_avoid_vehicle_data_in_hangar_loading(self) -> None:
        profiles = default_presence_profiles()

        self.assertEqual(tuple(profiles), PRESENCE_STATE_KEYS)
        self.assertEqual(profiles["hangar"].second_line_mode, "off")
        self.assertEqual(profiles["loading"].second_line_mode, "off")
        self.assertEqual(profiles["battle"].second_line_mode, "vehicle")
        self.assertEqual(profiles["test_drive"].second_line_mode, "vehicle")

    def test_legacy_settings_load_with_presence_defaults(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"refresh_interval": 7}', encoding="utf-8")

        self.assertEqual(load_refresh_interval(), 7)
        self.assertEqual(load_presence_profiles(), default_presence_profiles())

    def test_presence_profiles_round_trip_without_losing_refresh_interval(self) -> None:
        save_refresh_interval(9)
        profiles = default_presence_profiles()
        profiles["battle"] = PresenceProfile(
            "Combat",
            "custom",
            "Custom second line",
        )
        profiles["test_drive"] = PresenceProfile("", "off", "")
        save_presence_profiles(profiles)

        self.assertEqual(load_refresh_interval(), 9)
        self.assertEqual(load_presence_profiles(), profiles)

        save_refresh_interval(11)
        self.assertEqual(load_presence_profiles(), profiles)
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(saved["refresh_interval"], 11)
        self.assertIn("presence", saved)

    def test_missing_presence_profiles_are_filled_from_defaults(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            json.dumps({"presence": {"battle": {"first_line": "Fight"}}}),
            encoding="utf-8",
        )

        profiles = load_presence_profiles()
        self.assertEqual(profiles["battle"].first_line, "Fight")
        self.assertEqual(profiles["battle"].second_line_mode, "vehicle")
        self.assertEqual(profiles["hangar"], default_presence_profiles()["hangar"])

    def test_invalid_mode_text_and_state_keys_are_rejected(self) -> None:
        bad_profiles = default_presence_profiles()
        bad_profiles["battle"] = PresenceProfile("Fight", "guess", "")
        with self.assertRaises(ValueError):
            save_presence_profiles(bad_profiles)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"presence": {"extra": {}, "battle": {}}}),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            load_presence_profiles()

        with self.assertRaises(ValueError):
            save_presence_profiles({"battle": PresenceProfile("", "off", "")})

    def test_line_modes_independently_disable_customize_and_use_vehicle(self) -> None:
        self.assertEqual(
            build_presence_lines(PresenceProfile("", "off", ""), "Panther"),
            (None, None),
        )
        self.assertEqual(
            build_presence_lines(
                PresenceProfile("Battle", "custom", "Objective"),
                "Panther",
            ),
            ("Battle", "Objective"),
        )
        self.assertEqual(
            build_presence_lines(
                PresenceProfile("Test drive", "vehicle", ""),
                "Panther",
            ),
            ("Test drive", "Panther"),
        )
        self.assertEqual(
            build_presence_lines(
                PresenceProfile("Test drive", "vehicle", ""),
                None,
            ),
            ("Test drive", None),
        )

    def test_custom_templates_substitute_known_live_values(self) -> None:
        self.assertEqual(
            build_presence_lines(
                PresenceProfile(
                    "Flying",
                    "custom",
                    "{vehicle}[ · IAS {ias}][ · TAS {tas}]",
                ),
                "Spitfire",
                {
                    "vehicle": "Spitfire",
                    "ias": "420 km/h",
                    "tas": None,
                    "speed": "420 km/h",
                    "kills": None,
                },
            ),
            ("Flying", "Spitfire · IAS 420 km/h"),
        )

    def test_unavailable_template_values_remove_optional_segments(self) -> None:
        self.assertEqual(
            build_presence_lines(
                PresenceProfile(
                    "Flying",
                    "custom",
                    "[Speed: {speed} | ][Kills: {kills}]",
                ),
                None,
                {},
            ),
            ("Flying", None),
        )


if __name__ == "__main__":
    unittest.main()
