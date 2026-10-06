import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import user_map_registry
from map_catalog import find_map_name, find_map_name_from_metadata
from register_map import print_level_candidates, register_current_map
from user_map_registry import (
    MAX_MAP_NAME_LENGTH,
    MAX_REGISTRY_BYTES,
    MAX_REGISTRY_ENTRIES,
    find_registered_map,
    register_map,
)


class UserMapRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.registry_file = self.root / "WarThunderRS" / "map_names.json"
        self.registry_patch = patch(
            "user_map_registry.registry_path",
            return_value=self.registry_file,
        )
        self.registry_patch.start()
        self.addCleanup(self.registry_patch.stop)

    def test_registry_path_uses_appdata_subdirectory(self) -> None:
        original_registry_path = user_map_registry.registry_path
        self.registry_patch.stop()
        try:
            with patch.dict(os.environ, {"APPDATA": str(self.root)}):
                self.assertEqual(
                    original_registry_path(),
                    self.root / "WarThunderRS" / "map_names.json",
                )
        finally:
            self.registry_patch.start()

    def test_register_persists_name_and_optional_user_chosen_level_id(self) -> None:
        register_map("ABCDEF0123456789", "  Confirmed   Map Title  ", "level_123")

        self.assertEqual(find_registered_map("abcdef0123456789"), "Confirmed Map Title")
        self.assertEqual(
            json.loads(self.registry_file.read_text(encoding="utf-8")),
            {
                "abcdef0123456789": {
                    "name": "Confirmed Map Title",
                    "level_id": "level_123",
                }
            },
        )
        self.assertEqual(list(self.registry_file.parent.iterdir()), [self.registry_file])

    def test_atomic_replace_failure_preserves_previous_registry(self) -> None:
        register_map("0000000000000001", "First map")
        original = self.registry_file.read_bytes()
        with patch("user_map_registry.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                register_map("0000000000000002", "Second map")

        self.assertEqual(self.registry_file.read_bytes(), original)
        self.assertEqual(list(self.registry_file.parent.iterdir()), [self.registry_file])

    def test_invalid_fingerprint_name_and_level_id_are_rejected(self) -> None:
        for fingerprint in ("", "1234", "../123456789abc", "g" * 16):
            with self.subTest(fingerprint=fingerprint):
                with self.assertRaises(ValueError):
                    register_map(fingerprint, "Map")
        for name in (" ", "x" * (MAX_MAP_NAME_LENGTH + 1), "line\nbreak"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    register_map("0000000000000001", name)
        for level_id in ("../map", "level/id", "x" * 129):
            with self.subTest(level_id=level_id):
                with self.assertRaises(ValueError):
                    register_map("0000000000000001", "Map", level_id)
        self.assertFalse(self.registry_file.exists())

    def test_entry_and_file_size_limits_are_enforced_without_overwriting_data(self) -> None:
        too_many = {
            f"{index:016x}": {"name": "Map", "level_id": None}
            for index in range(MAX_REGISTRY_ENTRIES + 1)
        }
        self.registry_file.parent.mkdir(parents=True)
        self.registry_file.write_text(json.dumps(too_many), encoding="utf-8")
        original = self.registry_file.read_bytes()
        with self.assertRaises(ValueError):
            register_map("ffffffffffffffff", "New map")
        self.assertEqual(self.registry_file.read_bytes(), original)

        self.registry_file.write_bytes(b" " * (MAX_REGISTRY_BYTES + 1))
        with self.assertRaises(ValueError):
            find_registered_map("0000000000000001")
        with self.assertRaises(ValueError):
            register_map("0000000000000001", "Map")

    def test_corrupt_registry_does_not_override_static_catalog_fallback(self) -> None:
        self.registry_file.parent.mkdir(parents=True)
        self.registry_file.write_text("{invalid", encoding="utf-8")
        with patch(
            "map_catalog.CATALOG_PATH",
            Path(__file__).resolve().parents[1] / "map_catalog.json",
        ):
            self.assertEqual(
                find_map_name("0000002c7ebdffff"),
                "[Dominacja #1] Kvarken Południowy",
            )

    def test_explicit_metadata_wins_and_registry_precedes_static_catalog(self) -> None:
        register_map("0000002c7ebdffff", "User-confirmed Kvarken label")

        metadata_name = find_map_name_from_metadata(
            {"valid": True, "mapName": "API title"},
            None,
        )
        with patch(
            "map_catalog.CATALOG_PATH",
            Path(__file__).resolve().parents[1] / "map_catalog.json",
        ):
            self.assertEqual(
                find_map_name("0000002c7ebdffff"),
                "User-confirmed Kvarken label",
            )
        self.assertEqual(
            metadata_name or find_map_name("0000002c7ebdffff"),
            "API title",
        )

    def test_level_directory_listing_marks_stems_as_unconfirmed_candidates(self) -> None:
        levels_dir = self.root / "levels"
        levels_dir.mkdir()
        (levels_dir / "test_level_1.bin").write_bytes(b"untouched")
        (levels_dir / "not-a-level.txt").write_text("untouched", encoding="utf-8")
        output = io.StringIO()

        print_level_candidates(levels_dir, output)

        result = output.getvalue()
        self.assertIn("none is verified as the active map", result)
        self.assertIn('"test_level_1" -> suggested label "Test Level 1"', result)
        self.assertNotIn("not-a-level", result)
        self.assertEqual((levels_dir / "test_level_1.bin").read_bytes(), b"untouched")

    def test_registration_uses_active_local_map_fingerprint(self) -> None:
        output = io.StringIO()
        with patch(
            "register_map.read_active_map_fingerprint",
            return_value=("1234567890abcdef", (2048, 2048)),
        ):
            registered_fingerprint = register_current_map(
                "User-confirmed map",
                "candidate_level",
                output=output,
            )

        self.assertEqual(registered_fingerprint, "1234567890abcdef")
        self.assertEqual(
            find_registered_map(registered_fingerprint),
            "User-confirmed map",
        )
        self.assertIn("User-chosen level ID: candidate_level", output.getvalue())


if __name__ == "__main__":
    unittest.main()
