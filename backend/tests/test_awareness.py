import unittest
import pandas as pd
from core import awareness


class AwarenessColumnTests(unittest.TestCase):
    def test_exact_columns_win_over_partial_prefix_matches(self):
        frame = pd.DataFrame({"P1": ["Alfa"], "P10": ["Beta"], "P1 texto": ["Gamma"]})
        self.assertEqual(awareness.find_col(frame, "P1"), "P1")
        self.assertEqual(awareness.find_cols(frame, "P1\nP10"), ["P1", "P10"])

    def test_duplicate_demo_and_tom_selection_does_not_break_calculation(self):
        frame = pd.DataFrame({"TOM": ["Alfa", "Beta"], "P10": ["Beta", "Alfa"]})
        output, indicators, raw_columns = awareness.build_analysis(
            frame,
            {"sexo": "TOM", "edad": None, "departamento": None, "estrato": None, "ingreso": None},
            {"name": "A", "tom": "TOM", "esp": "P10", "ayu": "0"},
            ["Alfa", "Beta"], {"Alfa": ["alfa"], "Beta": ["beta"]}, [], 0,
        )
        self.assertEqual(raw_columns, ["TOM", "P10"])
        self.assertEqual(indicators[("Alfa", "TOM")].tolist(), [1, 0])
        self.assertEqual(len(output), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
