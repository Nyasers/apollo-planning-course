import unittest

from apollo_claw.deepseek import fallback_explain


class FallbackTest(unittest.TestCase):
    def test_empty_record_is_explained_from_facts(self):
        result = fallback_explain({
            "record": {"channel_count": 0, "status": "empty"},
            "metrics": {},
            "errors": [{"message": "record contains 0 channels"}],
        })
        self.assertIn("record 核心 channel 数量：0", result["facts"])
        self.assertTrue(any("SimControl" in item for item in result["suggestions"]))
        self.assertIn("experiment.errors", result["source_refs"])
