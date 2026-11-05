import os
import unittest
from unittest.mock import patch

from app import ratelimit
from app.ratelimit import SlidingWindowLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class SlidingWindowLimiterTests(unittest.TestCase):
    def test_allows_up_to_the_limit_then_blocks_with_retry_after(self):
        clock = FakeClock()
        limiter = SlidingWindowLimiter(clock)
        for _ in range(3):
            self.assertEqual(limiter.check("u", 3, 60), (True, 0))
        allowed, retry_after = limiter.check("u", 3, 60)
        self.assertFalse(allowed)
        self.assertEqual(retry_after, 60)

    def test_window_slides_and_allows_again(self):
        clock = FakeClock()
        limiter = SlidingWindowLimiter(clock)
        for _ in range(2):
            limiter.check("u", 2, 60)
        self.assertFalse(limiter.check("u", 2, 60)[0])
        clock.now += 61
        self.assertTrue(limiter.check("u", 2, 60)[0])

    def test_keys_are_independent(self):
        limiter = SlidingWindowLimiter(FakeClock())
        limiter.check("a", 1, 60)
        self.assertFalse(limiter.check("a", 1, 60)[0])
        self.assertTrue(limiter.check("b", 1, 60)[0])

    def test_retry_after_counts_down(self):
        clock = FakeClock()
        limiter = SlidingWindowLimiter(clock)
        limiter.check("u", 1, 60)
        clock.now += 20
        allowed, retry_after = limiter.check("u", 1, 60)
        self.assertFalse(allowed)
        self.assertEqual(retry_after, 40)

    def test_purge_removes_idle_keys(self):
        clock = FakeClock()
        limiter = SlidingWindowLimiter(clock)
        limiter.check("old", 5, 10)
        clock.now += 100
        limiter._calls = 499  # la siguiente llamada dispara la limpieza
        limiter.check("new", 5, 10)
        self.assertNotIn("old", limiter._hits)
        self.assertIn("new", limiter._hits)


class EnforceTests(unittest.TestCase):
    def setUp(self):
        ratelimit.limiter.reset()

    def test_disabled_flag_skips_limits(self):
        with patch.dict(os.environ, {"RATE_LIMIT_DISABLED": "1"}):
            for _ in range(50):
                ratelimit.enforce("t", "k", 1, 60)

    def test_client_ip_prefers_forwarded_header(self):
        class Request:
            headers = {"x-forwarded-for": "203.0.113.7, 10.0.0.1"}
            client = None

        self.assertEqual(ratelimit.client_ip(Request()), "203.0.113.7")


if __name__ == "__main__":
    unittest.main(verbosity=2)
