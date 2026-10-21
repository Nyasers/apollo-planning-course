import unittest

from apollo_claw.ai_presentation import build_ai_presentation


class AiPresentationTest(unittest.TestCase):
    def test_builds_beginner_findings_actions_and_glossary(self):
        experiment = {
            "meta": {"experiment_id": "exp-1"},
            "score": {"value": 93.8, "passed_metrics": "9/9"},
            "metrics": {
                "max_jerk": 28.14,
                "jerk_p95": 0.62,
                "max_lon_accel": 3.11,
                "max_lat_accel": 0.01,
                "hard_brake": 0,
            },
        }
        grading = {
            "scenario_pass": True,
            "metrics": [{"name": "ReachEnd", "pass": True}],
        }
        result = build_ai_presentation(experiment, grading, {}, None, {"need_student_confirm": ["确认峰值来源"]})
        self.assertEqual(result["version"], 1)
        self.assertIn("场景已通过", result["headline"])
        self.assertTrue(any(item["id"] == "jerk" for item in result["findings"]))
        self.assertTrue(result["actions"])
        self.assertTrue(any(item["term"] == "max_jerk" for item in result["glossary"]))
        self.assertTrue(any("急刹" in item for item in result["questions"]))

    def test_critical_failure_forces_error_presentation(self):
        experiment = {
            "meta": {"experiment_id": "exp-2"},
            "score": {"value": 0, "passed_metrics": "8/9"},
            "metrics": {"max_jerk": 1.0},
        }
        grading = {"scenario_pass": False, "metrics": [{"name": "Collision", "pass": False}]}
        result = build_ai_presentation(experiment, grading, {}, 10.0, {})
        self.assertEqual(result["severity"], "error")
        self.assertEqual(result["findings"][0]["id"], "critical_gate")
        self.assertEqual(result["actions"][0]["priority"], 1)


if __name__ == "__main__":
    unittest.main()
