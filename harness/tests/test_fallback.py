import unittest
from unittest.mock import patch

from apollo_claw.config import Settings
from apollo_claw.deepseek import answer_report_question, fallback_explain, fallback_report_answer, redact_for_model


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

    def test_report_question_uses_deepseek_and_history(self):
        settings = Settings(deepseek_api_key="sk-test", deepseek_base_url="https://api.deepseek.com", deepseek_model="deepseek-chat")
        report = {"meta": {"experiment_id": "exp-1"}, "score": {"passed_metrics": "8/9"}, "lab": {"comparison": []}}
        response = {"choices": [{"message": {"content": "{\"answer\": \"TTC 还需要检查\", \"evidence\": [\"29/267\"], \"next_steps\": [\"回放\"], \"needs_confirmation\": []}"}}]}
        with patch("apollo_claw.deepseek._post_json", return_value=response) as post:
            result = answer_report_question(settings, report, "为什么没通过？", [{"role": "user", "content": "上一问"}])
        self.assertEqual(result["answer"], "TTC 还需要检查")
        self.assertEqual(result["evidence"], ["29/267"])
        payload = post.call_args.args[1]
        self.assertEqual(payload["model"], "deepseek-chat")
        self.assertEqual(payload["messages"][1]["content"], "上一问")
        self.assertIn("exp-1", payload["messages"][-1]["content"])

    def test_report_fallback_mentions_ttc_and_baseline(self):
        report = {
            "meta": {"scenario": "人行道避让"},
            "record": {"channel_count": 6},
            "metrics": {"max_jerk": 2.903, "hard_brake": 0},
            "score": {"passed_metrics": "8/9", "metrics": [{"name": "TTC", "pass": False, "fail": 29, "total": 267}]},
            "lab": {"comparison": [{"id": "ttc", "label": "TTC", "before": "FAIL", "after": "FAIL", "before_detail": "29/257", "after_detail": "29/267"}], "next_actions": ["检查减速"]},
        }
        ttc = fallback_report_answer(report, "这份报告为什么没有完全通过？")
        self.assertIn("TTC", ttc["answer"])
        self.assertTrue(any("29/267" in item for item in ttc["evidence"]))
        baseline = fallback_report_answer(report, "和基线相比改善了吗？")
        self.assertIn("改善", baseline["answer"])

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
