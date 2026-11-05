import unittest

from app.observability import scrub_event


class ScrubEventTests(unittest.TestCase):
    def test_removes_credentials_and_request_body(self):
        event = {"request": {
            "headers": {"Authorization": "Bearer abc", "X-LLM-API-Key": "sk-123", "Accept": "json"},
            "data": {"password": "secreto"},
        }}
        cleaned = scrub_event(event)
        headers = cleaned["request"]["headers"]
        self.assertEqual(headers["Authorization"], "[Filtered]")
        self.assertEqual(headers["X-LLM-API-Key"], "[Filtered]")
        self.assertEqual(headers["Accept"], "json")
        self.assertNotIn("data", cleaned["request"])

    def test_event_without_request_is_returned_unchanged(self):
        self.assertEqual(scrub_event({"message": "boom"}), {"message": "boom"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
