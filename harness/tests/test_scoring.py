import json
import unittest
from pathlib import Path

from apollo_claw.scoring import compute_self_score, threshold_score


class SelfScoreTest(unittest.TestCase):
    def test_threshold_score_is_linear(self):
        self.assertEqual(threshold_score(3.0, 3.0), 100.0)
        self.assertEqual(threshold_score(6.0, 3.0), 0.0)
        self.assertEqual(threshold_score(4.5, 3.0), 50.0)

    def test_perfect_metrics_and_comfort_score_100(self):
        score = {
            "metrics": [
                {"name": "SpeedLimit", "pass": True, "score": 100},
                {"name": "ReachEnd", "pass": True, "score": 100},
            ]
        }
        metrics = {
            "max_lon_accel": 1.0,
            "max_jerk": 1.0,
            "max_lat_accel": 1.0,
            "hard_brake": 0,
        }
        result = compute_self_score(score, metrics, scenario_pass=True)
        self.assertEqual(result["value"], 100.0)
        self.assertEqual(result["performance_score"], 100.0)
        self.assertEqual(result["comfort_score"], 100.0)
        self.assertTrue(result["gate_passed"])
        self.assertFalse(result["is_official"])

    def test_critical_failure_forces_zero(self):
        score = {"metrics": [{"name": "Collision", "pass": False, "score": 100}]}
        result = compute_self_score(score, {"max_jerk": 1.0}, scenario_pass=True)
        self.assertEqual(result["value"], 0.0)
        self.assertEqual(result["gate_status"], "FAIL")
        self.assertEqual(result["critical_failures"], ["Collision"])

    def test_without_comfort_uses_performance_score(self):
        score = {"metrics": [{"name": "SpeedLimit", "pass": True, "score": 90}]}
        result = compute_self_score(score, {}, scenario_pass=True)
        self.assertEqual(result["value"], 90.0)
        self.assertIsNone(result["comfort_score"])


    def test_competition_scenario_assets_are_packaged(self):
        root = Path(__file__).resolve().parents[1] / "apollo_claw" / "defaults"
        scenario = json.loads((root / "xh_2026_obstacle_stop.scenario.json").read_text(encoding="utf-8"))
        official = json.loads((root / "xh_2026_obstacle_stop.official-grading.json").read_text(encoding="utf-8"))
        self.assertIn("障碍物停车避让", scenario["descriptionEnTokens"][0])
        self.assertEqual(official["gradingInfo"]["score"], 100)
        self.assertEqual(official["gradingInfo"]["status"], "finish_pass")
if __name__ == "__main__":
    unittest.main()