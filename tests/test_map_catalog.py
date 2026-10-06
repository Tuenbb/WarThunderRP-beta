import unittest

from map_catalog import find_map_name, find_map_name_from_metadata


class MapNameResolutionTests(unittest.TestCase):
    def test_map_info_metadata_takes_precedence_over_mission_metadata(self) -> None:
        self.assertEqual(
            find_map_name_from_metadata(
                {"valid": True, "mapName": "Automatic map title"},
                {"map_title": "Mission map title"},
            ),
            "Automatic map title",
        )

    def test_map_metadata_in_nested_map_object_is_supported(self) -> None:
        self.assertEqual(
            find_map_name_from_metadata(
                {"valid": True, "map_info": {"name": "Nested map title"}},
                None,
            ),
            "Nested map title",
        )

    def test_map_title_in_nested_mission_metadata_is_supported(self) -> None:
        self.assertEqual(
            find_map_name_from_metadata(
                {"valid": True},
                {"mission": {"mapName": "Mission metadata title"}},
            ),
            "Mission metadata title",
        )

    def test_mission_map_title_is_used_but_objective_text_is_not_guessed(self) -> None:
        self.assertEqual(
            find_map_name_from_metadata(
                {"valid": True},
                {
                    "map_title": "Mission map title",
                    "objectives": [
                        {"text": "Capture Kvarken"},
                    ],
                },
            ),
            "Mission map title",
        )
        self.assertIsNone(
            find_map_name_from_metadata(
                {"valid": True},
                {
                    "status": "Kvarken",
                    "objectives": [{"text": "Kvarken"}],
                },
            )
        )

    def test_confirmed_fingerprint_is_fallback(self) -> None:
        self.assertEqual(
            find_map_name("0000002c7ebdffff"),
            "[Dominacja #1] Kvarken Południowy",
        )


if __name__ == "__main__":
    unittest.main()
