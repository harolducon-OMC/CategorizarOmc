import unittest

from app.cache import MISSING, ResultCache, TTLCache


class Clock:
    now = 100.0

    def __call__(self):
        return self.now


class TTLCacheTests(unittest.TestCase):
    def test_entries_expire(self):
        clock = Clock()
        cache = TTLCache(max_entries=5, ttl=10, clock=clock)
        cache.set("a", 1)
        self.assertEqual(cache.get("a"), 1)
        clock.now += 11
        self.assertIs(cache.get("a"), MISSING)

    def test_least_recently_used_entry_is_evicted(self):
        cache = TTLCache(max_entries=2, ttl=100, clock=Clock())
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")  # "b" pasa a ser la menos usada
        cache.set("c", 3)
        self.assertIs(cache.get("b"), MISSING)
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.get("c"), 3)


class ResultCacheTests(unittest.TestCase):
    def test_builder_runs_once_per_key(self):
        cache = ResultCache()
        calls = []

        def build():
            calls.append(1)
            return {"rows": [1, 2]}

        first = cache.get_or_build("k", 60, build)
        second = cache.get_or_build("k", 60, build)
        self.assertEqual(first, second)
        self.assertEqual(len(calls), 1)

    def test_new_key_recomputes(self):
        cache = ResultCache()
        self.assertEqual(cache.get_or_build("freq:1:t1", 60, lambda: 1), 1)
        self.assertEqual(cache.get_or_build("freq:1:t2", 60, lambda: 2), 2)  # otra marca de tiempo = datos nuevos


if __name__ == "__main__":
    unittest.main(verbosity=2)
