"""Focused regression checks for validation, identity and idempotence."""
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.api_client import flatten
from src.cleaner import clean
from src.files import read_json
from src.loader import load_twice
from src.validator import validate, validation_demo

ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = read_json(ROOT / "data/snapshot.json")
        cls.rows = flatten(cls.snapshot)

    def test_archive_cardinality(self):
        self.assertEqual(len(self.rows), 400)
        self.assertEqual(len({(r["kind"], r["period"], r["rank"]) for r in self.rows}), 400)

    def test_reject_incomplete_snapshot(self):
        with self.assertRaises(ValueError):
            flatten(dict(self.snapshot, pages=self.snapshot["pages"][:-1]))

    def test_negative_examples_isolated(self):
        demos = validation_demo(self.rows[0])
        self.assertEqual(len(demos), 4)
        self.assertTrue(all(case["errors"] for case in demos))

    def test_bad_json_types_are_quarantined_individually(self):
        original = self.rows[0]
        rows = [original] + [dict(original, listens=x) for x in [None, 1.0, "10", True]]
        valid, invalid = validate(rows)
        self.assertEqual(list(valid.index), [0])
        self.assertEqual([r["index"] for r in invalid], [1, 2, 3, 4])

    def test_normalization_and_duplicate_identity(self):
        row = dict(self.rows[0], mbid=None, artist_name="  Rene\u0301   Smith ")
        valid, _ = validate([row, dict(row, artist_name="René Smith")])
        frame, quality = clean(valid)
        self.assertEqual(len(frame), 1)
        self.assertEqual(quality["duplicates_removed"], 1)
        self.assertEqual(frame.artist_name.iloc[0], "René Smith")
        self.assertTrue(frame.entity_key.iloc[0].startswith("name:"))

    def test_separate_chart_positions_survive(self):
        valid, _ = validate([self.rows[0], dict(self.rows[0], rank=2)])
        frame, _ = clean(valid)
        self.assertEqual(len(frame), 2)
        self.assertEqual(frame.entity_key.nunique(), 1)

    def test_conflicting_chart_slot_rejected(self):
        valid, _ = validate([self.rows[0], dict(self.rows[0], listens=1)])
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            clean(valid)

    def test_idempotence_and_conflict_rollback(self):
        valid, _ = validate(self.rows[:2])
        frame, _ = clean(valid)
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "charts.db"
            evidence = load_twice(frame.iloc[:1], path)
            self.assertEqual([i["inserted"] for i in evidence["loads"]], [1, 0])
            self.assertEqual(evidence["loads"][0]["sha256"], evidence["loads"][1]["sha256"])
            changed = frame.copy()
            changed.loc[0, "listens"] = 1
            with self.assertRaisesRegex(ValueError, "differs"):
                load_twice(changed, path)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute("SELECT listens FROM chart_entries").fetchall(),
                                 [(self.rows[0]["listens"],)])


if __name__ == "__main__":
    unittest.main()
