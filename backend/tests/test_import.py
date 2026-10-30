import unittest
import pandas as pd
from fastapi import HTTPException
from app.services import _read_dataframe


class ImportTests(unittest.TestCase):
    def test_csv_import_strips_headers_and_keeps_rows(self):
        frame = _read_dataframe(b" Pregunta , Edad\nMe gusta,25\n", "encuesta.csv")
        self.assertEqual(frame.columns.tolist(), ["Pregunta", "Edad"])
        self.assertEqual(frame.to_dict(orient="records"), [{"Pregunta": "Me gusta", "Edad": 25}])

    def test_duplicate_headers_are_made_unique(self):
        frame = _read_dataframe(b"Marca,Marca\nA,B\n", "encuesta.csv")
        self.assertEqual(len(frame.columns), 2)
        self.assertEqual(len(set(frame.columns)), 2)

    def test_unsupported_extension_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            _read_dataframe(b"hello", "encuesta.txt")
        self.assertEqual(error.exception.status_code, 415)


if __name__ == "__main__":
    unittest.main(verbosity=2)
