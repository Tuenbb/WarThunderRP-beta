import io
import unittest
from unittest.mock import call, patch
from urllib.error import HTTPError, URLError

from probe_map import MAP_PROBE_ENDPOINTS, print_endpoint_responses
from warthunder_api import ResponseTooLargeError


class ProbeMapTests(unittest.TestCase):
    def test_requests_exact_endpoints_and_summarizes_object_and_array_shapes(self) -> None:
        output = io.StringIO()
        payloads = {
            "/state": {"valid": False, "map_id": 21, "hidden": "not displayed"},
            "/map_info.json": {"valid": True, "map_generation": 8},
            "/map_obj.json": [
                {"type": "ground_model", "icon": "Player", "map_id": 21},
                {"type": "capture_zone", "name": "A"},
                {"type": "spawn", "zone_id": 3},
                {"type": "extra", "secret": "not displayed"},
            ],
            "/indicators": {"army": "tank", "name": "not a candidate"},
        }

        with patch("probe_map.fetch_json_data", side_effect=payloads.__getitem__) as fetch:
            print_endpoint_responses(output=output)

        self.assertEqual(
            fetch.call_args_list,
            [call(endpoint) for endpoint in MAP_PROBE_ENDPOINTS],
        )
        result = output.getvalue()
        self.assertIn("Response fields (3):", result)
        self.assertIn('"map_generation": number', result)
        self.assertIn("Response structure: array (4 items)", result)
        self.assertIn("Item 0:", result)
        self.assertIn("Item 2:", result)
        self.assertNotIn("Item 3:", result)
        self.assertIn("$.map_id = 21", result)
        self.assertIn("$[1].name = \"A\"", result)
        self.assertIn("Candidate fields found: yes", result)
        self.assertIn("candidate search truncated", result)
        self.assertEqual(result.count("Candidate fields found:"), len(MAP_PROBE_ENDPOINTS))
        self.assertNotIn("not displayed", result)
        self.assertNotIn('"secret"', result)

    def test_endpoint_errors_are_safe_and_do_not_stop_later_requests(self) -> None:
        output = io.StringIO()
        errors = {
            "/state": HTTPError(
                "http://127.0.0.1:8111/state",
                404,
                "Not Found",
                {},
                io.BytesIO(b"do not reveal body"),
            ),
            "/map_info.json": ResponseTooLargeError("sensitive response content"),
            "/map_obj.json": URLError(TimeoutError("sensitive detail")),
        }

        with patch(
            "probe_map.fetch_json_data",
            side_effect=lambda endpoint: (
                (_ for _ in ()).throw(errors[endpoint])
                if endpoint in errors
                else {"valid": True}
            ),
        ) as fetch:
            print_endpoint_responses(output=output)
        errors["/state"].close()

        result = output.getvalue()
        self.assertIn("HTTP 404", result)
        self.assertIn("configured byte limit", result)
        self.assertIn("connection timed out", result)
        self.assertEqual(
            result.count("Candidate fields found: unavailable"),
            3,
        )
        self.assertNotIn("do not reveal body", result)
        self.assertNotIn("sensitive response content", result)
        self.assertNotIn("sensitive detail", result)
        self.assertIn('"valid"', result)
        self.assertEqual(fetch.call_count, len(MAP_PROBE_ENDPOINTS))

    def test_unapproved_endpoint_is_never_requested(self) -> None:
        output = io.StringIO()
        with patch("probe_map.fetch_json_data") as fetch:
            print_endpoint_responses(("/state", "/mission.json"), output)

        fetch.assert_called_once_with("/state")
        self.assertIn("endpoint is not allowed", output.getvalue())

    def test_only_exact_candidate_keys_are_reported_with_bounded_values(self) -> None:
        output = io.StringIO()
        payload = {
            "map_identifier": "excluded",
            "outer": {
                "MAP_NAME": "V" * 500,
                "zone_id": 2,
                "name": {"nested": "not scalar"},
            },
        }
        with patch(
            "probe_map.fetch_json_data",
            side_effect=lambda endpoint: payload,
        ):
            print_endpoint_responses(("/state",), output)

        result = output.getvalue()
        self.assertIn("$.outer.MAP_NAME =", result)
        self.assertIn("$.outer.zone_id = 2", result)
        self.assertIn("Candidate fields found: yes", result)
        self.assertNotIn("$.map_identifier", result)
        self.assertNotIn("excluded", result)
        self.assertNotIn("nested", result)
        self.assertNotIn("V" * 81, result)
        self.assertIn("...", result)

    def test_report_output_stays_under_the_terminal_paste_limit(self) -> None:
        output = io.StringIO()
        wide_object = {
            f"field_{index}_" + "k" * 40: "value" * 100
            for index in range(30)
        }
        payloads = {
            "/state": {**wide_object, "map_id": "m" * 500},
            "/map_info.json": {**wide_object, "map_name": "n" * 500},
            "/map_obj.json": [
                {
                    **wide_object,
                    "name": "o" * 500,
                    "zone_id": index,
                }
                for index in range(204)
            ],
            "/indicators": {**wide_object, "location": "l" * 500},
        }
        with patch(
            "probe_map.fetch_json_data",
            side_effect=payloads.__getitem__,
        ):
            print_endpoint_responses(output=output)

        self.assertLessEqual(len(output.getvalue()), 3000)


if __name__ == "__main__":
    unittest.main()
