# -*- coding: utf-8 -*-
"""Pruebas offline para extracción y normalización de marcas."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import brands
from core.coding import NSNR_LABEL, frequency_table, valid_base


class FakeLLM:
    fast = "fake-fast"

    def json(self, system, user, model=None, max_tokens=2000):
        payload = json.loads(user.split("Respuestas:\n", 1)[1])
        results = []
        for item in payload:
            text = item["texto"].lower()
            if "bancolonbia" in text:
                results.append({"id": item["id"], "marcas": ["Bancolonbia"]})
            elif "bancolombia" in text:
                results.append({"id": item["id"], "marcas": ["Bancolombia"]})
            elif "bbva" in text:
                results.append({"id": item["id"], "marcas": ["BBVA"]})
            elif "no coincide" in text:
                results.append({"id": item["id"], "marcas": []})
            elif "omitida" in text:
                continue
            else:
                results.append({"id": item["id"], "marcas": []})
        return {"resultados": results}


class BrandClassificationTests(unittest.TestCase):
    def setUp(self):
        self.llm = FakeLLM()

    def test_closed_catalog_and_none_are_distinct_from_nsnr(self):
        texts = [
            "Bancolombia", "Bancolonbia", "La marca es BBVA", "ninguna",
            "no sé", "", "respuesta no coincide", "respuesta omitida",
        ]
        labels = brands.extract_mentions(
            self.llm, "¿Qué banco recuerda?", texts,
            known_brands=["Bancolombia", "Davivienda"], workers=1,
        )
        self.assertEqual(labels, [
            ["Bancolombia"], ["Bancolombia"], [brands.OTHER_BRAND_LABEL],
            [brands.NINGUNA_LABEL], [NSNR_LABEL], [],
            [brands.NINGUNA_LABEL], [brands.NINGUNA_LABEL],
        ])

    def test_empty_rows_stay_empty_through_mapping_and_are_not_valid_base(self):
        raw = [[], [brands.NINGUNA_LABEL], [NSNR_LABEL], ["Bancolombia"]]
        labels = brands.apply_mapping(raw, {"Bancolombia": "Bancolombia"})
        self.assertEqual(labels, [[], [brands.NINGUNA_LABEL], [NSNR_LABEL], ["Bancolombia"]])
        self.assertEqual(valid_base(labels), 2)

    def test_none_label_is_not_a_brand_entity_or_mapping_row(self):
        raw = [[brands.NINGUNA_LABEL], [NSNR_LABEL], ["Bancolombia"]]
        mapping = brands.build_mapping(raw)
        self.assertEqual(mapping["Mención"].tolist(), ["Bancolombia"])
        labels = brands.apply_mapping(raw, {"Bancolombia": "Bancolombia"})
        self.assertEqual(labels, [[brands.NINGUNA_LABEL], [NSNR_LABEL], ["Bancolombia"]])
        entities, aliases = brands.entities_and_aliases(raw, {"Bancolombia": "Bancolombia"})
        self.assertEqual(entities, ["Bancolombia"])
        self.assertNotIn(brands.NINGUNA_LABEL, aliases)
        table = frequency_table(labels, ["Bancolombia", brands.NINGUNA_LABEL]).set_index("Categoría")
        self.assertEqual(table.loc[brands.NINGUNA_LABEL, "Menciones"], 1)
        self.assertEqual(valid_base(labels), 2)

    def test_unknown_catalog_brand_is_other_not_none(self):
        labels = brands.extract_mentions(self.llm, "¿Qué banco?", ["Bancolombia"], known_brands=["Davivienda"], workers=1)
        self.assertEqual(labels, [[brands.OTHER_BRAND_LABEL]])

    def test_only_none_or_nsnr_still_has_explicit_labels(self):
        texts = ["ninguna", "no recuerdo", "ningún banco"]
        labels = brands.extract_mentions(self.llm, "¿Qué banco?", texts, workers=1)
        self.assertEqual(labels, [[brands.NINGUNA_LABEL], [NSNR_LABEL], [brands.NINGUNA_LABEL]])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ClosedCatalogMixedMentionTests(unittest.TestCase):
    """Una marca fuera del catálogo es 'Otra', pero no borra las marcas del catálogo."""

    class _Llm:
        fast = "x"

        def json(self, system, user, model=None, max_tokens=0):
            import json
            payload = json.loads(user.split("Respuestas:\n")[-1])
            answers = {"Bancolombia y Scotiabank": ["Bancolombia", "Scotiabank"], "Scotiabank": ["Scotiabank"]}
            return {"resultados": [{"id": p["id"], "marcas": answers[p["texto"]]} for p in payload]}

    def test_out_of_catalog_is_otra_and_keeps_catalog_brand(self):
        rows = brands.extract_mentions(
            self._Llm(), "P1", ["Bancolombia y Scotiabank", "Scotiabank", "", "ns/nr"],
            known_brands=["Bancolombia", "Davivienda"],
        )
        self.assertEqual(rows[0], ["Bancolombia", "Otra"])
        self.assertEqual(rows[1], ["Otra"])
        self.assertEqual(rows[2], [])           # celda vacía permanece vacía
        self.assertEqual(rows[3], ["NS/NR"])


class FirstMentionOnlyTests(unittest.TestCase):
    class _Llm:
        fast = "x"
        seen_system = ""

        def json(self, system, user, model=None, max_tokens=0):
            import json
            type(self).seen_system = system
            payload = json.loads(user.split("Respuestas:\n")[-1])
            answers = {"Puma, Nike, Adidas": ["Puma", "Nike", "Adidas"], "Adidas y Nike": ["Adidas", "Nike"]}
            return {"resultados": [{"id": p["id"], "marcas": answers[p["texto"]]} for p in payload]}

    def test_first_only_keeps_first_mention_and_marks_external_as_otra(self):
        rows = brands.extract_mentions(
            self._Llm(), "CE1", ["Puma, Nike, Adidas", "Adidas y Nike"],
            known_brands=["Nike", "Adidas"], first_only=True,
        )
        self.assertEqual(rows, [["Otra"], ["Adidas"]])
        self.assertIn("PRIMERA", self._Llm.seen_system)

    def test_default_keeps_all_catalog_brands(self):
        rows = brands.extract_mentions(self._Llm(), "CE1", ["Adidas y Nike"], known_brands=["Nike", "Adidas"])
        self.assertEqual(rows, [["Adidas", "Nike"]])
