import unittest

from probe_battle_metadata import (
    _safe_error_reason,
    describe_endpoint,
)
from warthunder_api import ApiResponseError


class BattleMetadataProbeTests(unittest.TestCase):
    def test_map_info_shows_only_map_metadata_values(self) -> None:
        lines = describe_endpoint(
            "/map_info.json",
            {
                "valid": True,
                "map_name": "Known map",
                "player_name": "Private name",
            },
        )
        output = "\n".join(lines)

        self.assertIn("Known map", output)
        self.assertNotIn("Private name", output)

    def test_map_object_schema_reports_player_marker_but_redacts_ids(self) -> None:
        lines = describe_endpoint(
            "/map_obj.json",
            [
                {
                    "id": "hidden-object-id",
                    "is_player": True,
                    "type": "ship",
                    "player_id": "hidden-player-id",
                }
            ],
        )
        output = "\n".join(lines)

        self.assertIn("is_player: True", output)
        self.assertIn("type: 'ship'", output)
        self.assertNotIn("hidden-object-id", output)
        self.assertNotIn("hidden-player-id", output)
        self.assertIn("object_types=", output)
        self.assertIn("explicit_player_boolean_fields=is_player=1", output)

    def test_map_object_summary_scans_all_records_for_ship_and_player_fields(self) -> None:
        records = [
            {"type": "capture_zone", "x": 1},
            {"type": "ship", "unit_id": "sensitive"},
            {"type": "ship", "player_controlled": True},
        ]

        output = "\n".join(describe_endpoint("/map_obj.json", records))

        self.assertIn('"ship": 2', output)
        self.assertIn("player_controlled(bool)", output)
        self.assertIn("explicit_player_boolean_fields=player_controlled=1", output)
        self.assertNotIn("sensitive", output)

    def test_mission_shows_bounded_escaped_status_and_objective_text(self) -> None:
        lines = describe_endpoint(
            "/mission.json",
            {
                "status": "status\x1b[31m",
                "objectives": [
                    {"primary": True, "text": "Objective \n text"},
                    {"text": "x" * 200},
                ],
            },
        )
        output = "\n".join(lines)

        self.assertIn(r'status="status\u001b[31m"', output)
        self.assertIn(r'objectives[0].text="Objective \n text"', output)
        self.assertIn(r'objectives[1].text="', output)
        self.assertNotIn("x" * 200, output)
        self.assertIn("active_primary_count=1", output)

    def test_safe_endpoint_error_does_not_echo_arbitrary_body_text(self) -> None:
        self.assertEqual(
            _safe_error_reason(ValueError("response body secret")),
            "ValueError",
        )
        self.assertIn(
            "Invalid JSON",
            _safe_error_reason(ApiResponseError("Invalid JSON")),
        )

    def test_safe_endpoint_error_reports_json_root_type_only(self) -> None:
        self.assertEqual(
            _safe_error_reason(
                ApiResponseError(
                    "Oczekiwano obiektu JSON; otrzymano list"
                )
            ),
            '"Oczekiwano obiektu JSON; otrzymano list"',
        )

    def test_schema_redacts_dynamic_mapping_keys(self) -> None:
        lines = describe_endpoint(
            "/map_obj.json",
            {"objects": {"private_object_123": {"type": "ship"}}},
        )

        self.assertNotIn("private_object_123", "\n".join(lines))

    def test_schema_output_is_bounded(self) -> None:
        data = {f"field_{index}": index for index in range(100)}

        output = "\n".join(describe_endpoint("/map_obj.json", data))

        self.assertIn("remaining keys omitted", output)
        self.assertLessEqual(len(output.splitlines()), 12)


if __name__ == "__main__":
    unittest.main()
