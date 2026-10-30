import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.coding import SENTIMENT_CODEFRAME, classify, valid_base

class NoCallLLM:
    fast = "fake"
    def json(self, *args, **kwargs):
        raise AssertionError("La coincidencia del diccionario no debe invocar el LLM")

class DictionaryClassificationTests(unittest.TestCase):
    def test_dictionary_matches_normalized_keywords_without_model_call(self):
        labels, stats = classify(NoCallLLM(), "¿Qué opina?", ["Me encanta el servicio al cliente"],
            [{"nombre": "Atención", "descripcion": "", "palabras_clave": "servicio al cliente, soporte"}], workers=1)
        self.assertEqual(labels, [["Atención"]])
        self.assertEqual(stats["unclassified"], 0)

    def test_blank_answer_stays_blank_and_explicit_nsnr_is_labelled(self):
        labels, _ = classify(NoCallLLM(), "¿Qué opina?", ["", "   ", "NS/NR"],
            [{"nombre": "Atención", "descripcion": "", "palabras_clave": "soporte"}], workers=1)
        self.assertEqual(labels, [[], [], ["NS/NR"]])
        self.assertEqual(valid_base(labels), 0)

    def test_sentiment_catalog_is_fixed_and_shared(self):
        labels = [item["nombre"] for item in SENTIMENT_CODEFRAME]
        self.assertEqual(labels, ["Positivo", "Neutral", "Negativo", "Mixto/ambivalente"])
        self.assertEqual(len(labels), len(set(labels)))

if __name__ == "__main__":
    unittest.main()
