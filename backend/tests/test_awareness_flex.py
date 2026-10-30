import io
import unittest

import pandas as pd
from openpyxl import load_workbook

from core import awareness_flex


class AwarenessFlexTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({
            "F1 Sexo": ["F", "M", "F"],
            "P1 Marca": ["Alfa", "Beta", "ninguna"],
            "P1A.1 Otras": ["Beta", "", "Alfa"],
            "P2.1 Alfa": ["1", "", "1"],
        })
        self.config = awareness_flex.parse_config({
            "entities": ["Alfa", "Beta"],
            "aliases": {"Alfa": ["alfa"], "Beta": ["beta"]},
            "demographics": {"sexo": "F1"},
            "analyses": [{"name": "Test", "tom": "P1 ", "esp": "P1A", "ayu": "P2"}, {"name": "Off"}],
        })

    def test_presets_have_three_modes(self):
        self.assertEqual(set(awareness_flex.presets()), {"bancos", "conglomerados", "personalizado"})

    def test_validation_detects_columns(self):
        rows = awareness_flex.detect_columns(list(self.frame.columns), self.config)
        tom = next(r for r in rows if r["campo"] == "TOM")
        self.assertEqual(tom["columnas"], "P1 Marca")

    def test_report_is_valid_xlsx_with_expected_sheets(self):
        data = awareness_flex.generate_report(self.frame, self.config)
        workbook = load_workbook(io.BytesIO(data))
        self.assertIn("Resumen Demográficos", workbook.sheetnames)
        self.assertIn("Test", workbook.sheetnames)
        self.assertNotIn("Off", workbook.sheetnames)

    def test_requires_entities_and_one_active_analysis(self):
        with self.assertRaises(ValueError):
            awareness_flex.parse_config({"entities": []})
        config = awareness_flex.parse_config({"entities": ["A"]})
        with self.assertRaises(ValueError):
            awareness_flex.generate_report(self.frame, config)


if __name__ == "__main__":
    unittest.main(verbosity=2)
