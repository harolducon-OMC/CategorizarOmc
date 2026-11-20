"""Protección contra ReDoS: los patrones de normalización llegan desde la interfaz y no pueden colgar el servidor."""
import json
import time
import unittest

from core import awareness, awareness_flex


class RegexSafetyTests(unittest.TestCase):
    def test_nested_and_backtracking_patterns_are_rejected(self):
        for pattern in (r"(a+)+$", r"(a|a)+$", r"(.*)*x", r"(\w+\s?)*$", r"(a)\1", "[", "x" * 300):
            with self.subTest(pattern=pattern[:20]):
                self.assertFalse(awareness.is_safe_regex(pattern))

    def test_simple_patterns_and_platform_presets_are_accepted(self):
        for pattern in (r".*foo.*", r"(?i)^marca\s+uno$", r"(?i)\bnike\b"):
            with self.subTest(pattern=pattern):
                self.assertTrue(awareness.is_safe_regex(pattern))
        for group in (awareness.BANK_NORMALIZATIONS, awareness.CONGLOMERATE_NORMALIZATIONS):
            for item in group:
                self.assertTrue(awareness.is_safe_regex(item["pattern"]), item["pattern"])

    def test_malicious_pattern_is_ignored_instead_of_hanging(self):
        started = time.perf_counter()
        result = awareness.apply_normalizations("a" * 60 + "!", [{"pattern": r"(a+)+$", "replacement": "X"}])
        self.assertLess(time.perf_counter() - started, 1.0)
        self.assertEqual(result, "a" * 60 + "!")  # sin normalización: el patrón no se ejecutó

    def test_presets_still_normalize(self):
        self.assertEqual(awareness.apply_normalizations("banco de bogota centro", awareness.BANK_NORMALIZATIONS), "Banco de Bogotá")

    def test_parse_config_rejects_dangerous_or_oversized_configuration(self):
        base = {"entities": ["Nike", "Adidas"]}
        awareness_flex.parse_config(json.dumps(base))  # una configuración normal sigue siendo válida
        bad_configs = {
            "regex peligrosa": {**base, "normalizations": [{"pattern": "(a+)+$", "replacement": "X"}]},
            "demasiadas marcas": {"entities": [f"marca {i}" for i in range(awareness_flex.MAX_ENTITIES + 1)]},
            "marca larguísima": {"entities": ["x" * (awareness_flex.MAX_NAME_CHARS + 1)]},
            "normalización no es objeto": {**base, "normalizations": ["texto"]},
            "marcas no es lista": {"entities": "Nike"},
        }
        for label, config in bad_configs.items():
            with self.subTest(label), self.assertRaises(ValueError):
                awareness_flex.parse_config(json.dumps(config))


if __name__ == "__main__":
    unittest.main()
