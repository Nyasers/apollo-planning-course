import unittest

from apollo_claw.lab_report import build_lab_report, to_markdown


class LabReportTest(unittest.TestCase):
    def _report(self, exp_id, reach_pass, jerk, ttc_score=100):
        return {
            "meta": {"experiment_id": exp_id, "task": "crosswalk", "scenario": "人行道避让", "created_at": "2026-10-18T23:00:00+08:00", "source": "local-harness", "mode": "real", "status": "evaluated"},
            "environment": {},
            "record": {"channel_count": 6, "message_count": 1000, "duration_sec": 25},
            "metrics": {"max_jerk": jerk, "hard_brake": 0},
            "score": {"source": "apollo-claw-selfeval", "value": None, "is_official": False, "scenario_pass": False, "passed_metrics": "7/9", "metrics": [
                {"name": "ReachEnd", "pass": reach_pass, "score": 100 if reach_pass else 0, "fail": 0 if reach_pass else 10, "total": 10},
                {"name": "TTC", "pass": False, "score": ttc_score, "fail": 2, "total": 10},
            ]},
            "ai": {}, "verification": {}, "capability": {},
            "evidence": [
                {"type": "record", "path": "/apollo_workspace/data/record/base.record"},
                {"type": "record", "path": "/apollo_workspace/data/record/base.record.00000.1"},
                {"type": "channel_report", "path": "report"},
            ],
            "commands": [{"purpose": "raw"}],
        }

    def test_bundle_builds_comparison_and_cleans_contract(self):
        current = self._report("current", True, 2.9)
        baseline = self._report("baseline", False, 12.36, ttc_score=100)
        lab = build_lab_report(current, baseline, "人工核验：目标 3060 是行人。")
        self.assertEqual(lab["score"]["metrics"][1]["score"], None)
        self.assertEqual(len([item for item in lab["evidence"] if item["type"] == "record"]), 1)
        self.assertNotIn("commands", lab)
        self.assertIn("human_review", lab["lab"])
        self.assertIn("行人", lab["lab"]["human_review"][0])
        rows = {item["id"]: item for item in lab["lab"]["comparison"]}
        self.assertEqual(rows["reachend"]["status"], "improved")
        self.assertEqual(rows["jerk"]["status"], "improved")
        self.assertIn("人工核验", to_markdown(lab))
