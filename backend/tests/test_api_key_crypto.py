import os
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.security import decrypt_api_key, encrypt_api_key

class ApiKeyCryptoTests(unittest.TestCase):
    def test_ciphertext_round_trips_and_does_not_contain_plaintext(self):
        secret = "t" * 64
        with patch("app.security.JWT_SECRET", secret):
            plaintext = "sk-example-provider-secret"
            ciphertext = encrypt_api_key(plaintext)
            self.assertNotIn(plaintext, ciphertext)
            self.assertEqual(decrypt_api_key(ciphertext), plaintext)

    def test_secret_rotation_fails_closed(self):
        ciphertext = None
        with patch("app.security.JWT_SECRET", "a" * 64):
            ciphertext = encrypt_api_key("private-token")
        with patch("app.security.JWT_SECRET", "b" * 64):
            with self.assertRaises(RuntimeError):
                decrypt_api_key(ciphertext)

if __name__ == "__main__":
    unittest.main()
