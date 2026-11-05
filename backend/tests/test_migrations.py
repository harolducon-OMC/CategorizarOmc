import re
import unittest
from pathlib import Path

VERSIONS = Path(__file__).resolve().parent.parent / "alembic" / "versions"


class MigrationChainTests(unittest.TestCase):
    def test_there_is_a_single_head_and_no_gaps(self):
        revisions, parents = {}, set()
        for path in VERSIONS.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            revision = re.search(r'^revision\s*=\s*"([^"]+)"', text, re.M)
            down = re.search(r'^down_revision\s*=\s*(None|"([^"]+)")', text, re.M)
            self.assertIsNotNone(revision, path.name)
            self.assertIsNotNone(down, path.name)
            revisions[revision.group(1)] = down.group(2)
            if down.group(2):
                parents.add(down.group(2))
        self.assertTrue(revisions, "No hay migraciones")
        heads = set(revisions) - parents
        self.assertEqual(len(heads), 1, f"Debe haber una sola cabeza, hay: {sorted(heads)}")
        for parent in parents:
            self.assertIn(parent, revisions, f"Falta la migración padre {parent}")
        self.assertEqual([r for r, d in revisions.items() if d is None], ["0001_baseline"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
