import unittest
from types import SimpleNamespace as NS

import pandas as pd

from core import awareness

TOM = "P1. ¿Qué marca deportiva recuerda primero?"
ESP1 = "P2_1 ¿Qué otras marcas recuerda?"
ESP2 = "P2_2 ¿Qué otras marcas recuerda?"


def survey():
    return pd.DataFrame({
        TOM: ["decathlon", "Gef y Nike", "xx raro", "", "Nike", "decatlon"],
        ESP1: ["Gef", "", "Decathlon, Nike", "Nike", "", "Gef"],
        ESP2: ["", "", "", "Gef", "", ""],
        "P3_Decathlon": ["1", "", "1", "", "1", ""],
        "P3_Gef": ["", "1", "", "1", "1", "1"],
        "P3_Nike": ["1", "", "", "", "", ""],
        "P9 Edad": ["20", "30", "40", "50", "60", "70"],
    })


def tom_class(labels=None):
    return NS(question=TOM, kind="brands", labels=labels or [["Decathlon"], ["Gef"], ["Gef"], [], ["Nike"], ["Decathlon"]])


ENTITIES = ["Decathlon", "Gef", "Nike"]
ALIASES = {"Decathlon": ["decathlon", "decatlon"], "Gef": ["gef"], "Nike": ["nike"]}
NO_DEMO = {key: None for key in ("sexo", "edad", "departamento", "estrato", "ingreso")}


def awa(frame, tom="P1", esp="P2", ayu="P3"):
    cfg = {"name": "A", "tom": tom, "esp": esp, "ayu": ayu}
    _, indicators, _ = awareness.build_analysis(frame, NO_DEMO, cfg, ENTITIES, ALIASES, [], 0)
    table = awareness.category_table(indicators, frame, None, None, ENTITIES)
    return table.set_index("Entidad")


class ResolveColumnsTests(unittest.TestCase):
    def test_codes_are_resolved_to_real_columns(self):
        columns = awareness.resolve_columns(survey(), "P1", ["P2"], ["P3"])
        self.assertEqual(columns["tom"], [TOM])
        self.assertEqual(columns["esp"], [ESP1, ESP2])
        self.assertEqual(columns["ayu"], ["P3_Decathlon", "P3_Gef", "P3_Nike"])
        self.assertEqual(columns["unmatched"], [])

    def test_zero_and_blank_codes_mean_no_question(self):
        columns = awareness.resolve_columns(survey(), "0", [], ["0", " "])
        self.assertEqual((columns["tom"], columns["esp"], columns["ayu"], columns["unmatched"]), ([], [], [], []))
        self.assertEqual(awareness.clean_codes(["0", "P2", ""]), ["P2"])

    def test_unknown_codes_are_reported(self):
        columns = awareness.resolve_columns(survey(), "P7", ["P2"], [])
        self.assertEqual(columns["unmatched"], ["P7"])

    def test_only_one_tom_code_is_allowed(self):
        columns = awareness.resolve_columns(survey(), "P1\nP2", [], [])
        self.assertEqual(columns["extra_tom"], ["P2"])


class CategorizedDataTests(unittest.TestCase):
    def test_saved_labels_replace_the_raw_text_in_the_calculation(self):
        raw = awa(survey())
        categorized = awa(awareness.frame_with_categorized_responses(survey(), [tom_class()]))
        # La fila 3 dice «xx raro»: el texto no coincide con ninguna marca, pero la etiqueta guardada sí
        self.assertAlmostEqual(raw.loc["Gef", "TOM %"], 1 / 6)
        self.assertAlmostEqual(categorized.loc["Gef", "TOM %"], 2 / 6)

    def test_manual_corrections_are_used(self):
        corrected = tom_class([["Decathlon"], ["Gef"], ["Nike"], [], ["Nike"], ["Decathlon"]])
        result = awa(awareness.frame_with_categorized_responses(survey(), [corrected]))
        self.assertAlmostEqual(result.loc["Nike", "TOM %"], 2 / 6)

    def test_sources_report_which_columns_use_the_categorization(self):
        columns = awareness.resolve_columns(survey(), "P1", ["P2"], [])
        esp1 = NS(question=ESP1, kind="brands", labels=[["Gef"], [], ["Decathlon", "Nike"], ["Nike"], [], ["Gef"]])
        sources = awareness.categorization_sources(survey(), columns, [tom_class(), esp1])
        by_column = {row["column"]: row for row in sources}
        self.assertEqual(by_column[TOM]["source"], "categorizado")
        self.assertEqual(by_column[TOM]["answered"], 5)
        self.assertEqual(by_column[TOM]["labeled"], 5)
        self.assertEqual(by_column[ESP1]["source"], "categorizado")
        self.assertEqual(by_column[ESP2]["source"], "texto original")
        self.assertIsNone(by_column[ESP2]["labeled"])

    def test_labels_from_a_different_number_of_rows_are_flagged_as_stale(self):
        columns = awareness.resolve_columns(survey(), "P1", [], [])
        sources = awareness.categorization_sources(survey(), columns, [tom_class([["Gef"]])])
        self.assertTrue(sources[0]["stale"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
