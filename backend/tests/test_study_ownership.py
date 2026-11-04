import unittest
from unittest.mock import Mock

from fastapi import HTTPException

from app.main import _class_or_404
from app.models import Study
from app.services import get_study


class StudyOwnershipTests(unittest.TestCase):
    def test_study_lookup_filters_by_study_and_owner(self):
        database = Mock()
        database.scalar.return_value = None

        with self.assertRaises(HTTPException) as error:
            get_study(database, "study-123", "user-456")

        self.assertEqual(error.exception.status_code, 404)
        statement = str(database.scalar.call_args.args[0])
        self.assertIn("studies.id", statement)
        self.assertIn("studies.owner_id", statement)

    def test_owned_study_is_returned(self):
        database = Mock()
        expected = Study(
            id="study-123", owner_id="user-456", name="Survey",
            source_filename="survey.csv", columns=["Q1"], row_count=1,
        )
        database.scalar.return_value = expected

        self.assertIs(get_study(database, "study-123", "user-456"), expected)

    def test_classification_lookup_is_scoped_through_its_study(self):
        database = Mock()
        database.scalar.return_value = None

        with self.assertRaises(HTTPException) as error:
            _class_or_404(database, "classification-123", "user-456")

        self.assertEqual(error.exception.status_code, 404)
        statement = str(database.scalar.call_args.args[0])
        self.assertIn("JOIN studies", statement)
        self.assertIn("studies.owner_id", statement)


if __name__ == "__main__":
    unittest.main()
