import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from diagnostic_report import (
    DIAGNOSTIC_ENDPOINTS,
    build_diagnostic_report,
    save_diagnostic_report,
    serialize_diagnostic_report,
)


class DiagnosticReportTests(unittest.TestCase):
    def test_report_contains_only_redacted_summary_fields(self) -> None:
        private_vehicle_id = "tankModels/private_vehicle_identifier"
        private_map_name = "Private Map Name"
        private_player_token = "private-player-token"
        responses = {
            "/state": {"valid": True, "player": private_player_token},
            "/indicators": {
                "valid": True,
                "type": private_vehicle_id,
                "army": "tank",
                "name": private_player_token,
            },
            "/map_info.json": {
                "valid": True,
                "map_name": private_map_name,
                "map_id": "private-map-id",
            },
            "/mission.json": {
                "objectives": [{"primary": True, "text": private_map_name}],
            },
            "/map_obj.json": [{"player_id": private_player_token}],
        }
        seen: list[str] = []

        def fetcher(endpoint: str) -> object:
            seen.append(endpoint)
            return responses[endpoint]

        report = build_diagnostic_report(
            fetcher=fetcher,
            game_detector=lambda: True,
            now=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        encoded = serialize_diagnostic_report(report).decode("utf-8")

        self.assertEqual(seen, list(DIAGNOSTIC_ENDPOINTS))
        self.assertEqual(report["presence_state"], "battle")
        self.assertEqual(report["vehicle"], {"known": True, "class": "ground"})
        self.assertEqual(
            report["map"],
            {"metadata_title_known": True, "source": "local_metadata"},
        )
        self.assertEqual(
            report["planned_assets"]["vehicle_image_host"],
            "static.encyclopedia.warthunder.com",
        )
        self.assertNotIn(private_vehicle_id, encoded)
        self.assertNotIn(private_map_name, encoded)
        self.assertNotIn(private_player_token, encoded)
        self.assertNotIn("private-map-id", encoded)
        self.assertNotIn("username", encoded.casefold())
        self.assertNotIn("APPDATA", encoded)

    def test_endpoint_failures_include_exception_class_without_message(self) -> None:
        private_path = r"C:\Users\Alice\private"

        def fetcher(endpoint: str) -> object:
            if endpoint == "/state":
                raise OSError(private_path)
            return {}

        report = build_diagnostic_report(
            fetcher=fetcher,
            game_detector=lambda: False,
        )
        encoded = serialize_diagnostic_report(report).decode("utf-8")

        self.assertEqual(
            report["endpoints"]["/state"],
            {"reachable": False, "error_class": "OSError"},
        )
        self.assertNotIn(private_path, encoded)
        self.assertNotIn("Alice", encoded)

    def test_report_json_is_utf8_and_bounded(self) -> None:
        report = build_diagnostic_report(
            fetcher=lambda _endpoint: None,
            game_detector=lambda: False,
        )

        encoded = serialize_diagnostic_report(report)
        self.assertLessEqual(len(encoded), 32 * 1024)
        self.assertTrue(encoded.endswith(b"\n"))
        json.loads(encoded.decode("utf-8"))

    def test_report_saves_as_utf8_json(self) -> None:
        report = build_diagnostic_report(
            fetcher=lambda _endpoint: {},
            game_detector=lambda: False,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            save_diagnostic_report(path, report)

            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(saved["application"]["version"], "0.2.0-beta.1")


if __name__ == "__main__":
    unittest.main()
