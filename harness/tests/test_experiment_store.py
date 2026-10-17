import json
import tempfile
import unittest
from pathlib import Path

from apollo_claw.experiment import ExperimentStore


class ExperimentStoreTest(unittest.TestCase):
    def test_create_load_and_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(Path(tmp))
            exp = store.create("crosswalk", "人行道避让")
            self.assertEqual(exp["meta"]["task"], "crosswalk")
            loaded = store.load(exp["meta"]["experiment_id"])
            self.assertEqual(loaded["meta"]["scenario"], "人行道避让")
            self.assertEqual(len(store.list()), 1)

    def test_evidence_and_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(Path(tmp))
            exp = store.create("crosswalk", "人行道避让", "20261017-120000-abcdef-crosswalk")
            store.add_evidence(exp, "record", "record/crosswalk.record", "demo")
            store.save(exp)
            self.assertEqual(store.load(exp["meta"]["experiment_id"])["evidence"][0]["type"], "record")
            with self.assertRaises(ValueError):
                store.sandbox_path(exp["meta"]["experiment_id"], "../outside")
