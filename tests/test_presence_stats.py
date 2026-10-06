import unittest

from presence_stats import extract_presence_values


class PresenceStatsTests(unittest.TestCase):
    def test_aircraft_speed_values_are_formatted_from_valid_state(self) -> None:
        self.assertEqual(
            extract_presence_values(
                {"valid": True, "IAS, km/h": 412, "TAS, km/h": 530},
                "Example aircraft",
            ),
            {
                "vehicle": "Example aircraft",
                "speed": "412 km/h",
                "ias": "412 km/h",
                "tas": "530 km/h",
                "kills": None,
            },
        )

    def test_speed_falls_back_to_tas_and_ignores_invalid_values(self) -> None:
        self.assertEqual(
            extract_presence_values(
                {"valid": True, "IAS, km/h": "n/a", "TAS, km/h": 300.5},
                None,
            )["speed"],
            "300.5 km/h",
        )
        self.assertIsNone(
            extract_presence_values(
                {"valid": False, "IAS, km/h": 400},
                "Example aircraft",
            )["ias"]
        )
        self.assertIsNone(
            extract_presence_values(
                {"valid": True, "IAS, km/h": True},
                None,
            )["speed"]
        )


if __name__ == "__main__":
    unittest.main()
