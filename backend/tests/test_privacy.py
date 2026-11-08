import os
import unittest
from unittest.mock import patch

from core.privacy import redact_enabled, redact_pii


class RedactPiiTests(unittest.TestCase):
    def test_hides_common_personal_data(self):
        text = ("Escríbame a ana.perez@correo.com o llame al 300 123 4567 / +57 3105556677. "
                "Mi cédula es 1.012.345.678 y también 1012345678. Mire https://perfil.com/ana y www.sitio.co")
        result = redact_pii(text)
        for leaked in ("ana.perez", "300 123 4567", "3105556677", "1.012.345.678", "1012345678", "perfil.com", "sitio.co"):
            self.assertNotIn(leaked, result)
        for marker in ("[CORREO]", "[TELEFONO]", "[DOCUMENTO]", "[ENLACE]"):
            self.assertIn(marker, result)

    def test_card_numbers_are_hidden(self):
        self.assertIn("[NUMERO]", redact_pii("Mi tarjeta 4111 1111 1111 1111 venció"))

    def test_survey_numbers_are_kept(self):
        text = "Tengo 25 años, voy 3 veces al mes y compré en 2024 por 150.000 pesos"
        self.assertEqual(redact_pii(text), text)

    def test_empty_values_are_returned_unchanged(self):
        self.assertEqual(redact_pii(""), "")
        self.assertIsNone(redact_pii(None))

    def test_can_be_disabled_by_environment(self):
        with patch.dict(os.environ, {"AI_REDACT_PII": "0"}):
            self.assertFalse(redact_enabled())
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AI_REDACT_PII", None)
            self.assertTrue(redact_enabled())


if __name__ == "__main__":
    unittest.main(verbosity=2)
