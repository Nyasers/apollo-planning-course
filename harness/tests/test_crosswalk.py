import tempfile
import unittest
from pathlib import Path

from apollo_claw.crosswalk import find_stop_pose, load_calibration, measure_distance, save_calibration


class CrosswalkDistanceTest(unittest.TestCase):
    def test_find_stop_pose_prefers_crosswalk_wait_over_final_parking(self):
        rows = []
        t = 0.0
        for speed, x in [(3.0, 110.0), (2.0, 105.0), (0.1, 100.0), (0.1, 100.0), (1.5, 98.0), (0.0, 90.0), (0.0, 90.0)]:
            rows.append({"t": t, "x": x, "y": 1.0, "heading": 3.141592653589793, "speed_mps": speed})
            t += 1.5
        stop = find_stop_pose(rows)
        self.assertIsNotNone(stop)
        self.assertAlmostEqual(stop["x"], 100.0)
        self.assertGreaterEqual(stop["duration_sec"], 1.0)

    def test_measure_distance_from_calibration_and_relative_stop(self):
        calibration = {
            "experiment_id": "calibration-run",
            "distance_m": 1.5,
            "reference": "front_bumper_to_crosswalk_near_edge",
            "stop_pose": {"x": 100.0, "y": 0.0, "heading": 3.141592653589793},
        }
        same = measure_distance("calibration-run", {"x": 100.0, "y": 0.0}, calibration)
        self.assertEqual(same["distance_m"], 1.5)
        self.assertTrue(same["pass"])
        closer = measure_distance("next-run", {"x": 99.7, "y": 0.0}, calibration)
        self.assertAlmostEqual(closer["distance_m"], 1.2)
        self.assertFalse(closer["pass"])
        farther = measure_distance("next-run", {"x": 100.2, "y": 0.0}, calibration)
        self.assertAlmostEqual(farther["distance_m"], 1.7)
        self.assertTrue(farther["pass"])

    def test_calibration_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "crosswalk-calibration.json"
            pose = {"t": 10.0, "x": 100.0, "y": 2.0, "heading": 3.14}
            save_calibration(path, "run-1", 1.5, pose)
            loaded = load_calibration(path)
            self.assertEqual(loaded["experiment_id"], "run-1")
            self.assertEqual(loaded["distance_m"], 1.5)
            self.assertEqual(loaded["stop_pose"]["x"], 100.0)


if __name__ == "__main__":
    unittest.main()
