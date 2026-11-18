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


class _Client:
    host = "192.0.2.50"


def _request(forwarded=None, client=_Client):
    class Request:
        headers = {"x-forwarded-for": forwarded} if forwarded is not None else {}

    Request.client = client
    return Request()


class EnforceTests(unittest.TestCase):
    def setUp(self):
        ratelimit.limiter.reset()

    def test_disabled_flag_skips_limits(self):
        with patch.dict(os.environ, {"RATE_LIMIT_DISABLED": "1"}):
            for _ in range(50):
                ratelimit.enforce("t", "k", 1, 60)


class ClientIpTests(unittest.TestCase):
    def test_default_uses_last_forwarded_entry(self):
        # La IP de la derecha la añade el proxy de confianza (Render).
        with patch.dict(os.environ, {"TRUSTED_PROXY_HOPS": "1"}):
            req = _request("198.51.100.9, 203.0.113.7")
            self.assertEqual(ratelimit.client_ip(req), "203.0.113.7")

    def test_spoofed_left_entry_is_ignored(self):
        # Un cliente que escribe su propia cabecera no puede elegir la IP que se cuenta.
        with patch.dict(os.environ, {"TRUSTED_PROXY_HOPS": "1"}):
            req = _request("1.2.3.4, 203.0.113.7")
            self.assertEqual(ratelimit.client_ip(req), "203.0.113.7")

    def test_two_hops_counts_from_the_right(self):
        with patch.dict(os.environ, {"TRUSTED_PROXY_HOPS": "2"}):
            req = _request("198.51.100.9, 203.0.113.7, 10.0.0.1")
            self.assertEqual(ratelimit.client_ip(req), "203.0.113.7")

    def test_zero_hops_ignores_header_and_uses_connection_ip(self):
        with patch.dict(os.environ, {"TRUSTED_PROXY_HOPS": "0"}):
            req = _request("203.0.113.7")
            self.assertEqual(ratelimit.client_ip(req), "192.0.2.50")

    def test_without_header_falls_back_to_connection_ip(self):
        with patch.dict(os.environ, {"TRUSTED_PROXY_HOPS": "1"}):
            self.assertEqual(ratelimit.client_ip(_request()), "192.0.2.50")

    def test_without_header_or_client_returns_unknown(self):
        with patch.dict(os.environ, {"TRUSTED_PROXY_HOPS": "1"}):
            self.assertEqual(ratelimit.client_ip(_request(client=None)), "desconocido")

    def test_invalid_hops_value_defaults_to_one(self):
        with patch.dict(os.environ, {"TRUSTED_PROXY_HOPS": "abc"}):
            req = _request("198.51.100.9, 203.0.113.7")
            self.assertEqual(ratelimit.client_ip(req), "203.0.113.7")


if __name__ == "__main__":
    unittest.main(verbosity=2)
