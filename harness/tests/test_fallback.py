import unittest

from apollo_claw.deepseek import fallback_explain, redact_for_model


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

    def test_model_input_is_redacted(self):
        data = redact_for_model({
            "commands": ["secret command output"],
            "logs": [{"path": r"C:\Users\FQX\secret.log", "excerpt": "DEEPSEEK_API_KEY=sk-abcdefghijklmnop"}],
            "record": {"path": "/home/fqx/application-pnc/data/record/x"},
        })
        self.assertNotIn("commands", data)
        self.assertNotIn("fqx", data["logs"][0]["path"])
        self.assertNotIn("sk-abcdefghijklmnop", data["logs"][0]["excerpt"])
        self.assertNotIn("/home/fqx", data["record"]["path"])
