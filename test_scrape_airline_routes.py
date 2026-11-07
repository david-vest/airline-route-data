import json
import unittest
from unittest.mock import Mock, patch

from curl_cffi import requests

from scrape_airline_routes import fetch, parse_airports, parse_metadata


def response(body, status=200, headers=None):
    result = Mock(status_code=status, headers=headers or {}, text=body,
                  content=body.encode())
    result.json.side_effect = lambda: json.loads(body)
    if status >= 400:
        result.raise_for_status.side_effect = requests.RequestsError(f"HTTP {status}")
    return result


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.sleep = patch("scrape_airline_routes.time.sleep").start()
        self.addCleanup(patch.stopall)

    def test_airport_list(self):
        self.session.get.return_value = response(
            '{"response":{"airports":[{"IATA":"LHR"}]}}'
        )
        data = fetch(self.session, "https://example.com/airports", parse_airports)
        self.assertEqual(data["response"]["airports"][0]["IATA"], "LHR")
        self.session.get.assert_called_once_with(
            "https://example.com/airports", timeout=30
        )

    def test_transient_challenge_retries(self):
        self.session.get.side_effect = [
            response("challenge", 403, {"cf-mitigated": "challenge"}),
            response('{"response":{"airports":[{"IATA":"LHR"}]}}'),
        ]
        fetch(self.session, "https://example.com/airports", parse_airports)
        self.assertEqual(self.session.get.call_count, 2)
        self.sleep.assert_called_once_with(5)

    def test_persistent_challenge_fails_with_actionable_error(self):
        self.session.get.return_value = response("<script>window._cf_chl_opt = {};</script>")
        with self.assertRaisesRegex(RuntimeError, "FLIGHTSFROM_PROXY"):
            fetch(self.session, "https://example.com/airports", parse_airports)
        self.assertEqual(self.session.get.call_count, 3)

    def test_network_errors_are_bounded(self):
        self.session.get.side_effect = requests.RequestsError("Timed out")
        with self.assertRaisesRegex(RuntimeError, "after 3 attempts"):
            fetch(self.session, "https://example.com/airports", parse_airports)
        self.assertEqual(self.session.get.call_count, 3)

    def test_invalid_or_empty_airport_list_is_not_success(self):
        for body in ("<html>Error</html>", '{}', '{"response":{"airports":[]}}'):
            with self.subTest(body=body):
                self.session.get.return_value = response(body)
                with self.assertRaises(RuntimeError):
                    fetch(self.session, "https://example.com/airports", parse_airports)

    def test_missing_airport_is_skipped(self):
        self.session.get.return_value = response("Not found", 404)
        self.assertIsNone(fetch(self.session, "https://example.com/OLD", parse_metadata,
                                allow_not_found=True))
        self.sleep.assert_not_called()

    def test_airport_list_404_is_not_skipped(self):
        self.session.get.return_value = response("Not found", 404)
        with self.assertRaises(RuntimeError):
            fetch(self.session, "https://example.com/airports", parse_airports)

    def test_destination_metadata(self):
        metadata = parse_metadata(response(
            '{"response":{"airport":{"IATA":"LHR"},"routes":[]}}'
        ))
        self.assertEqual(metadata, {"airport": {"IATA": "LHR"}, "routes": []})

    def test_missing_metadata_is_bounded(self):
        self.session.get.return_value = response('{"response":{}}')
        with self.assertRaisesRegex(RuntimeError, "airport and routes"):
            fetch(self.session, "https://example.com/LHR", parse_metadata)
        self.assertEqual(self.session.get.call_count, 3)


if __name__ == "__main__":
    unittest.main()
