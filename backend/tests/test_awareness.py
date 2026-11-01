import unittest
import pandas as pd
from core import awareness


class AwarenessColumnTests(unittest.TestCase):
    def test_brand_matching_trims_whitespace_and_uses_explicit_aliases(self):
        self.assertTrue(awareness.contains_entity(
            "  Sportfitness  ", "Sport fitness",
            {"Sport fitness": ["Sportfitness"]},
        ))
        self.assertFalse(awareness.contains_entity("Decatlon", "Decathlon", {}))

    def test_exact_columns_win_over_partial_prefix_matches(self):
        frame = pd.DataFrame({"P1": ["Alfa"], "P10": ["Beta"], "P1 texto": ["Gamma"]})
        self.assertEqual(awareness.find_col(frame, "P1"), "P1")
        self.assertEqual(awareness.find_cols(frame, "P1\nP10"), ["P1", "P10"])

    def test_question_groups_include_delimited_suffixes_but_not_neighboring_codes(self):
        frame = pd.DataFrame(columns=["A1_2", "A10", "A1", "A1_1", "A12"])
        self.assertEqual(awareness.find_cols(frame, "A1"), ["A1", "A1_1", "A1_2"])

    def test_tom_uses_the_single_column_selected_by_the_reference_logic(self):
        frame = pd.DataFrame({
            "CE1": ["Alfa", "", None, "0"],
            "CE1_1": ["Beta", "Beta", "", "Alfa"],
            "CE1_2": ["Beta", "Alfa", "Alfa", "Alfa"],
            "CE10": ["Beta", "Beta", "Beta", "Beta"],
        })
        _, indicators, raw_columns = awareness.build_analysis(
            frame, {},
            {"name": "TOM", "tom": "CE1", "esp": "0", "ayu": "0"},
            ["Alfa", "Beta"], {"Alfa": ["alfa"], "Beta": ["beta"]}, [], 0,
        )
        self.assertIn("CE1", raw_columns)
        self.assertNotIn("CE1_1", raw_columns)
        self.assertNotIn("CE1_2", raw_columns)
        self.assertNotIn("CE10", raw_columns)
        self.assertEqual(indicators[("Alfa", "TOM")].tolist(), [1, 0, 0, 0])
        self.assertEqual(indicators[("Beta", "TOM")].tolist(), [0, 0, 0, 0])

    def test_spontaneous_groups_delimited_splits_without_neighboring_codes(self):
        frame = pd.DataFrame({
            "E1": ["Alfa", "", ""],
            "E1_1": ["Alfa", "Alfa", ""],
            "E10": ["Alfa", "", "Alfa"],
        })
        _, indicators, raw_columns = awareness.build_analysis(
            frame, {},
            {"name": "AWA", "tom": "0", "esp": "E1", "ayu": "0"},
            ["Alfa"], {"Alfa": ["alfa"]}, [], 0,
        )
        self.assertNotIn("E10", raw_columns)
        self.assertEqual(indicators[("Alfa", "Espontaneo")].tolist(), [1, 1, 0])
        self.assertEqual(indicators[("Alfa", "Ayudado")].tolist(), [0, 0, 0])

    def test_aided_uses_last_entity_column_assigned_by_reference_logic(self):
        frame = pd.DataFrame({
            "H1 Alfa": ["1", "1"],
            "H1_1 Alfa": ["", "1"],
            "H10 Alfa": ["1", ""],
        })
        _, indicators, raw_columns = awareness.build_analysis(
            frame, {},
            {"name": "AWA", "tom": "0", "esp": "0", "ayu": "H1"},
            ["Alfa"], {"Alfa": ["alfa"]}, [], 0,
        )
        self.assertNotIn("H10 Alfa", raw_columns)
        self.assertEqual(indicators[("Alfa", "Ayudado")].tolist(), [0, 1])

    def test_categorized_labels_replace_raw_response_but_keep_empty_rows_blank(self):
        frame = pd.DataFrame({"C1": ["Alias antiguo", "", "Otra respuesta"]})
        cleaned = awareness.frame_with_categorized_responses(frame, [{
            "question": "C1",
            "labels": [["Marca corregida"], ["No debe aparecer"], []],
        }])
        self.assertEqual(cleaned["C1"].tolist(), ["Marca corregida", None, None])

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


class TomFirstMentionTests(unittest.TestCase):
    def _tom(self, answers, entities=("Nike", "Adidas"), **cfg):
        frame = pd.DataFrame({"TOM": answers})
        aliases = {e: [e.lower()] for e in entities}
        config = {"name": "A", "tom": "TOM", "esp": "0", "ayu": "0", **cfg}
        _, indicators, _ = awareness.build_analysis(
            frame, {k: None for k in ("sexo", "edad", "departamento", "estrato", "ingreso")},
            config, list(entities), aliases, [], 0,
        )
        return {e: indicators[(e, "TOM")].tolist() for e in entities}

    def test_only_first_brand_counts_as_tom(self):
        result = self._tom(["Nike, Adidas", "Adidas y Nike", "Puma, Nike, Adidas", "Nike"])
        self.assertEqual(result["Nike"], [1, 0, 0, 1])
        self.assertEqual(result["Adidas"], [0, 1, 0, 0])   # "Puma" primero => nadie recibe TOM

    def test_alias_with_conjunction_is_not_split(self):
        result = self._tom(["Johnson y Johnson", "Nike"], entities=("Johnson y Johnson", "Nike"))
        self.assertEqual(result["Johnson y Johnson"], [1, 0])

    def test_first_only_can_be_disabled(self):
        result = self._tom(["Puma, Nike"], tom_first_only=False)
        self.assertEqual(result["Nike"], [1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
