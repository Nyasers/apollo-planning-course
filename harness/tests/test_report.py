import json
import tempfile
import unittest
from pathlib import Path

from apollo_claw.experiment import ExperimentStore
from apollo_claw.report import build_report, export_report, validate_report


class ReportTest(unittest.TestCase):
    def test_report_sanitizes_paths_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ExperimentStore(root)
            exp = store.create("crosswalk", "人行道避让", "20261017-120000-abcdef-crosswalk")
            exp["metrics"] = {"min_ttc": 1.4, "max_jerk": 4.8, "collision": False}
            exp["score"] = {"source": "demo", "value": 82, "is_official": False}
            exp["ai"] = {"facts": ["TTC 1.4s"], "suggestions": ["提前减速"]}
            exp["evidence"] = [{"type": "record", "path": str(root / "experiments" / exp["meta"]["experiment_id"] / "record" / "crosswalk.record"), "summary": "demo"}]
            report = build_report(exp, store.experiment_dir(exp["meta"]["experiment_id"]), home=Path.home())
            self.assertEqual(report["evidence"][0]["path"], "record/crosswalk.record")
            self.assertEqual(validate_report(report), [])
            out = store.experiment_dir(exp["meta"]["experiment_id"])
            json_path, md_path = export_report(report, out)
            self.assertTrue(json_path.exists())
            self.assertIn("Apollo Claw", md_path.read_text(encoding="utf-8"))

    def test_report_rejects_api_key(self):
        report = {
            "meta": {"experiment_id": "x", "task": "crosswalk", "scenario": "crosswalk", "created_at": "now", "source": "local-harness", "mode": "real"},
            "environment": {}, "record": {}, "metrics": {}, "ai": {}, "verification": {}, "evidence": [], "capability": {},
            "logs": "DEEPSEEK_API_KEY=sk-abcdefghijklmnop",
        }
        errors = validate_report(report)
        self.assertTrue(any("API-key" in error for error in errors))
