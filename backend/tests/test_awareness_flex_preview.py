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


if __name__ == "__main__":
    unittest.main(verbosity=2)
