import unittest

import pandas as pd
from core import awareness_flex


class AwarenessPreviewTests(unittest.TestCase):
    def test_preview_uses_report_calculation_and_selected_row_limit(self):
        frame = pd.DataFrame({
            "TOM": ["Alfa", "Beta", "Alfa"],
            "ESP": ["Beta", "Alfa", "Beta"],
            "AY Alfa": ["1", "", "1"],
            "AY Beta": ["", "1", ""],
        })
        config = {
            "entities": ["Alfa", "Beta"],
            "aliases": {"Alfa": ["alfa"], "Beta": ["beta"]},
            "normalizations": [],
            "demographics": {"sexo": "", "edad": "", "departamento": "", "estrato": "", "ingreso": ""},
            "analyses": [
                {"name": "AWA Marca", "tom": "TOM", "esp": "ESP", "ayu": "AY"},
                {"name": "Desactivado", "tom": "0", "esp": "0", "ayu": "0"},
            ],
            "max_rows": 2,
            "expected_raw_cols": 0,
        }

        result = awareness_flex.preview_results(frame, config)

        self.assertEqual(result["base"], 2)
        self.assertEqual([item["name"] for item in result["analyses"]], ["AWA Marca"])
        self.assertEqual(result["analyses"][0]["rows"][0]["Entidad"], "Alfa")
        self.assertEqual(result["analyses"][0]["rows"][0]["TOM %"], 0.5)
        self.assertEqual(result["analyses"][0]["rows"][0]["Espontaneo %"], 0.5)
        self.assertEqual(result["analyses"][0]["rows"][0]["AWA %"], 1.0)

    def test_tom_insights_compare_catalog_leader_with_unselected_mentions(self):
        frame = pd.DataFrame({
            "TOM": ["Alfa", "Bancolombia", "Bancolombiaa", "Alfa y Bancolombia", "Ninguna"],
        })

        result = awareness_flex.build_tom_insights(
            frame,
            {"tom": "TOM", "tom_first_only": True},
            ["Alfa"],
            {"Alfa": ["alfa"]},
            [],
            [{"Entidad": "Alfa", "TOM": 2, "TOM %": 0.4}],
        )

        self.assertEqual(result["marca_evaluada_lider"]["marca"], "Alfa")
        self.assertEqual(result["marca_evaluada_lider"]["menciones"], 2)
        self.assertEqual(result["marca_fuera_del_catalogo_lider"]["marca"], "Bancolombia")
        self.assertEqual(result["marca_fuera_del_catalogo_lider"]["menciones"], 2)
        self.assertEqual(result["base"], 5)
        self.assertEqual(result["respuestas_tom"], 4)

    def test_tom_insights_are_unavailable_without_a_tom_column(self):
        result = awareness_flex.build_tom_insights(
            pd.DataFrame({"ESP": ["Alfa"]}),
            {"tom": "0"},
            ["Alfa"],
            {},
            [],
            [],
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
