import os
import unittest
from unittest.mock import patch
from app.db import _database_url


class DatabaseUrlTests(unittest.TestCase):
    def test_password_is_encoded_safely(self):
        with patch.dict(os.environ, {
            "DB_USER": "analyst", "DB_PASSWORD": "p@ss:/word", "DB_HOST": "db",
            "DB_PORT": "5432", "DB_NAME": "insights", "DATABASE_URL": "",
        }, clear=False):
            url = _database_url()
        rendered = url.render_as_string(hide_password=False)
        self.assertEqual(rendered, "postgresql+psycopg://analyst:p%40ss%3A%2Fword@db:5432/insights")


if __name__ == "__main__":
    unittest.main(verbosity=2)
