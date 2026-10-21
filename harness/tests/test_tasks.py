import json
import unittest
from pathlib import Path


class TaskManifestTest(unittest.TestCase):
    def test_packaged_tasks_cover_all_competition_experiments(self):
        path = Path(__file__).resolve().parents[1] / "apollo_claw" / "defaults" / "tasks.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        tasks = data["tasks"]
        expected_numbers = [
            "\u5b9e\u9a8c\u4e00",
            "\u5b9e\u9a8c\u4e8c",
            "\u5b9e\u9a8c\u4e09",
            "\u5b9e\u9a8c\u56db",
            "\u5b9e\u9a8c\u4e94",
            "\u5b9e\u9a8c\u516d",
            "\u5b9e\u9a8c\u4e03",
            "\u5b9e\u9a8c\u516b",
            "\u5b9e\u9a8c\u4e5d",
        ]
        self.assertEqual(len(tasks), 9)
        self.assertEqual([task["number"] for task in tasks], expected_numbers)
        self.assertEqual(sum(task.get("status") == "open" for task in tasks), 1)
        self.assertEqual(tasks[1]["id"], "crosswalk")
        self.assertEqual(tasks[-1]["title"], "\u81ea\u4e3b\u6cca\u8f66\u573a\u666f")

    def test_website_and_packaged_manifests_stay_in_sync(self):
        repo_root = Path(__file__).resolve().parents[2]
        site_path = repo_root / "site" / "harness" / "tasks.json"
        if not site_path.exists():
            self.skipTest("repository website manifest is not packaged")
        packaged_path = Path(__file__).resolve().parents[1] / "apollo_claw" / "defaults" / "tasks.json"
        site = json.loads(site_path.read_text(encoding="utf-8"))
        packaged = json.loads(packaged_path.read_text(encoding="utf-8"))
        self.assertEqual(site, packaged)


if __name__ == "__main__":
    unittest.main()
