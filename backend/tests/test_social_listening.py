import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from app.routers.social_listening import SOCIAL_KEY_IDS, SocialAnalysisPayload
from core.llm import PROVIDER_CONFIG
from core.social_listening import _mentions_brand, _parse_toon, _pick_created_at, _within_date_window, report


class SocialKeyIsolationTests(unittest.TestCase):
    def test_social_key_identifiers_are_unique_and_disjoint_from_llm_providers(self):
        social_ids = list(SOCIAL_KEY_IDS.values())
        self.assertEqual(len(social_ids), len(set(social_ids)))
        self.assertTrue(set(social_ids).isdisjoint(PROVIDER_CONFIG))
        self.assertEqual(set(SOCIAL_KEY_IDS), {"xpoz", "gemini", "groq"})

    def test_analysis_request_bounds_mentions_and_provider_choices(self):
        valid = SocialAnalysisPayload(brand="Marca", model="modelo-prueba")
        self.assertEqual(valid.max_mentions, 60)
        self.assertEqual(valid.provider, "gemini")
        with self.assertRaises(ValidationError):
            SocialAnalysisPayload(brand="Marca", model="modelo", max_mentions=201)
        with self.assertRaises(ValidationError):
            SocialAnalysisPayload(brand="Marca", model="modelo", provider="openrouter")


class SocialListeningCoreTests(unittest.TestCase):
    def test_created_at_is_normalized_to_utc_and_unix_milliseconds_are_supported(self):
        self.assertEqual(_pick_created_at({"createdAtDate": "2026-05-10T12:00:00Z"}), "2026-05-10T12:00:00+00:00")
        self.assertEqual(_pick_created_at({"created_utc": 1770000000000}), "2026-02-02T02:40:00+00:00")

    def test_date_window_excludes_old_and_undated_mentions(self):
        cutoff = datetime(2025, 11, 25, tzinfo=timezone.utc)
        self.assertTrue(_within_date_window({"created_at": "2026-01-01T00:00:00+00:00"}, cutoff))
        self.assertFalse(_within_date_window({"created_at": "2025-11-24T23:59:59+00:00"}, cutoff))
        self.assertFalse(_within_date_window({}, cutoff))

    def test_brand_match_is_case_and_accent_insensitive_and_word_bounded(self):
        self.assertTrue(_mentions_brand("Café Uno", "Me encanta CAFE UNO"))
        self.assertFalse(_mentions_brand("Mar", "La marca Maravilla"))

    def test_toon_rows_are_parsed_without_splitting_commas_inside_quotes(self):
        parsed = _parse_toon('data:\n  results[1]{id,text}:\n    1,"bueno, muy bueno"\n')
        self.assertEqual(parsed, [{"id": "1", "text": "bueno, muy bueno"}])

    def test_report_handles_no_mentions(self):
        result = report("Marca", [])
        self.assertEqual(result["total_menciones"], 0)
        self.assertEqual(result["score_promedio"], 0)
        self.assertEqual(result["alertas_riesgo"], [])


if __name__ == "__main__":
    unittest.main()
