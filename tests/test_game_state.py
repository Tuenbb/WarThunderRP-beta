import unittest

from game_state import (
    classify_presence_state,
    classify_state,
    presence_assets_enabled,
)


class InvalidIndicatorStateTests(unittest.TestCase):
    def test_presence_state_keys_are_stable_and_cover_supported_situations(self) -> None:
        self.assertEqual(
            classify_presence_state(
                True,
                {"valid": True, "type": "tankModels/example"},
                {"valid": False},
                {"objectives": []},
            ),
            "hangar",
        )
        self.assertEqual(
            classify_presence_state(
                True,
                {"valid": True, "type": "dummy_plane"},
                {"valid": True},
                {"objectives": []},
            ),
            "loading",
        )
        self.assertEqual(
            classify_presence_state(
                True,
                {"valid": False},
                {"valid": True},
                {"objectives": [{"primary": True}]},
            ),
            "battle",
        )
        self.assertEqual(
            classify_presence_state(
                True,
                {"valid": True, "type": "tankModels/example"},
                {"valid": True},
                {},
            ),
            "test_drive",
        )
        self.assertEqual(
            classify_presence_state(
                True,
                {"valid": True, "type": "tankModels/example"},
                {"valid": True},
                {"objectives": []},
            ),
            "test_drive",
        )
        self.assertEqual(
            classify_presence_state(
                True,
                {"valid": True, "type": "tankModels/example"},
                {"valid": True},
                {"objectives": [{"primary": False}]},
            ),
            "test_drive",
        )
        self.assertIsNone(
            classify_presence_state(
                False,
                None,
                None,
                None,
            )
        )

    def test_vehicle_assets_are_enabled_only_for_loaded_gameplay_states(self) -> None:
        self.assertTrue(presence_assets_enabled("hangar"))
        self.assertTrue(presence_assets_enabled("battle"))
        self.assertTrue(presence_assets_enabled("test_drive"))
        self.assertFalse(presence_assets_enabled("loading"))
        self.assertFalse(presence_assets_enabled(None))

    def test_active_primary_objective_and_valid_map_is_battle(self) -> None:
        self.assertEqual(
            classify_state(
                True,
                {"valid": False},
                {"valid": True},
                {"objectives": [{"primary": True}]},
            ),
            "Bitwa",
        )

    def test_battle_remains_detectable_when_indicators_endpoint_is_unavailable(self) -> None:
        self.assertEqual(
            classify_state(
                True,
                None,
                {"valid": True},
                {"objectives": [{"primary": True}]},
            ),
            "Bitwa",
        )

    def test_invalid_indicators_without_active_objective_remain_unavailable(self) -> None:
        self.assertEqual(
            classify_state(
                True,
                {"valid": False},
                {"valid": True},
                {"objectives": []},
            ),
            "Ładowanie lub dane pojazdu niedostępne",
        )

    def test_primary_objective_without_valid_map_does_not_claim_battle(self) -> None:
        self.assertEqual(
            classify_state(
                True,
                {"valid": False},
                {"valid": False},
                {"objectives": [{"primary": True}]},
            ),
            "Ładowanie lub dane pojazdu niedostępne",
        )

    def test_hangar_loading_and_test_drive_distinctions_remain(self) -> None:
        self.assertEqual(
            classify_state(
                True,
                {"valid": True, "type": "tankModels/example"},
                {"valid": False},
                {"objectives": []},
            ),
            "Hangar",
        )
        self.assertEqual(
            classify_state(
                True,
                {"valid": True, "type": "dummy_plane"},
                {"valid": True},
                {"objectives": []},
            ),
            "Ładowanie do bitwy",
        )
        self.assertEqual(
            classify_state(
                True,
                {"valid": True, "type": "tankModels/example"},
                {"valid": True},
                {},
            ),
            "Test drive",
        )


if __name__ == "__main__":
    unittest.main()
