import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from pathlib import Path

from apollo_claw.config import Settings
from apollo_claw.experiment import ExperimentStore
from apollo_claw.server import make_handler


class WebActionTest(unittest.TestCase):
    def test_doctor_action_runs_as_background_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            tasks = Path(tmp) / "tasks.json"
            tasks.write_text(json.dumps({"tasks": [{"id": "crosswalk", "title": "人行道避让"}]}), encoding="utf-8")
            settings = Settings(tasks_file=str(tasks), output_dir=tmp)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(settings))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urllib.request.urlopen(base + "/api/session", timeout=5) as response:
                    token = json.loads(response.read().decode("utf-8"))["token"]
                body = json.dumps({"task": "crosswalk", "scenario": "人行道避让"}).encode("utf-8")
                request = urllib.request.Request(base + "/api/actions/doctor", data=body, method="POST")
                request.add_header("Content-Type", "application/json")
                request.add_header("X-Apollo-Claw-Token", token)
                with urllib.request.urlopen(request, timeout=10) as response:
                    action = json.loads(response.read().decode("utf-8"))
                job_id = action["job"]["job_id"]
                deadline = time.time() + 20
                job = {"status": "running"}
                while time.time() < deadline:
                    with urllib.request.urlopen(base + f"/api/jobs/{job_id}", timeout=5) as response:
                        job = json.loads(response.read().decode("utf-8"))
                    if job["status"] != "running":
                        break
                    time.sleep(0.3)
                self.assertIn(job["status"], {"succeeded", "failed"})
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_record_dry_run_action_creates_experiment(self):
        with tempfile.TemporaryDirectory() as tmp:
            tasks = Path(tmp) / "tasks.json"
            tasks.write_text(json.dumps({"tasks": [{"id": "crosswalk", "title": "人行道避让"}]}), encoding="utf-8")
            settings = Settings(tasks_file=str(tasks), output_dir=tmp)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(settings))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urllib.request.urlopen(base + "/api/session", timeout=5) as response:
                    token = json.loads(response.read().decode("utf-8"))["token"]
                body = json.dumps({"task": "crosswalk", "scenario": "人行道避让", "tag": "crosswalk", "seconds": 1, "execute": False}).encode("utf-8")
                request = urllib.request.Request(base + "/api/actions/record", data=body, method="POST")
                request.add_header("Content-Type", "application/json")
                request.add_header("X-Apollo-Claw-Token", token)
                with urllib.request.urlopen(request, timeout=10) as response:
                    action = json.loads(response.read().decode("utf-8"))
                job_id = action["job"]["job_id"]
                experiment_id = action["experiment_id"]
                deadline = time.time() + 20
                while time.time() < deadline:
                    with urllib.request.urlopen(base + f"/api/jobs/{job_id}", timeout=5) as response:
                        job = json.loads(response.read().decode("utf-8"))
                    if job["status"] != "running":
                        break
                    time.sleep(0.3)
                self.assertEqual(job["status"], "succeeded")
                with urllib.request.urlopen(base + f"/api/experiments/{experiment_id}", timeout=5) as response:
                    experiment = json.loads(response.read().decode("utf-8"))
                self.assertEqual(experiment["record"]["status"], "dry-run")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_explain_action_saves_fallback_ai(self):
        with tempfile.TemporaryDirectory() as tmp:
            tasks = Path(tmp) / "tasks.json"
            tasks.write_text(json.dumps({"tasks": [{"id": "crosswalk", "title": "人行道避让"}]}), encoding="utf-8")
            settings = Settings(tasks_file=str(tasks), output_dir=tmp, deepseek_api_key="")
            store = ExperimentStore(Path(tmp))
            exp = store.create("crosswalk", "人行道避让")
            exp_id = exp["meta"]["experiment_id"]
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(settings))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urllib.request.urlopen(base + "/api/session", timeout=5) as response:
                    token = json.loads(response.read().decode("utf-8"))["token"]
                body = json.dumps({"experiment_id": exp_id, "question": "分析当前证据"}).encode("utf-8")
                request = urllib.request.Request(base + "/api/actions/explain", data=body, method="POST")
                request.add_header("Content-Type", "application/json")
                request.add_header("X-Apollo-Claw-Token", token)
                with urllib.request.urlopen(request, timeout=10) as response:
                    action = json.loads(response.read().decode("utf-8"))
                job_id = action["job"]["job_id"]
                deadline = time.time() + 20
                job = {"status": "running"}
                while time.time() < deadline:
                    with urllib.request.urlopen(base + f"/api/jobs/{job_id}", timeout=5) as response:
                        job = json.loads(response.read().decode("utf-8"))
                    if job["status"] != "running":
                        break
                    time.sleep(0.3)
                self.assertEqual(job["status"], "succeeded")
                with urllib.request.urlopen(base + f"/api/experiments/{exp_id}", timeout=5) as response:
                    experiment = json.loads(response.read().decode("utf-8"))
                self.assertEqual(experiment["ai"]["mode"], "fallback")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_deepseek_settings_can_be_saved_and_cleared(self):
        with tempfile.TemporaryDirectory() as tmp:
            tasks = Path(tmp) / "tasks.json"
            tasks.write_text(json.dumps({"tasks": [{"id": "crosswalk", "title": "人行道避让"}]}), encoding="utf-8")
            env_path = Path(tmp) / ".env"
            settings = Settings(tasks_file=str(tasks), output_dir=tmp, deepseek_api_key="")
            old_key = os.environ.pop("DEEPSEEK_API_KEY", None)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(settings))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urllib.request.urlopen(base + "/api/session", timeout=5) as response:
                    token = json.loads(response.read().decode("utf-8"))["token"]
                headers = {"Content-Type": "application/json", "X-Apollo-Claw-Token": token}
                body = json.dumps({"api_key": "sk-test-1234567890", "base_url": "https://api.deepseek.com", "model": "deepseek-chat"}).encode("utf-8")
                with patch("apollo_claw.server._deepseek_settings_path", return_value=env_path):
                    request = urllib.request.Request(base + "/api/settings/deepseek", data=body, method="POST", headers=headers)
                    with urllib.request.urlopen(request, timeout=5) as response:
                        saved = json.loads(response.read().decode("utf-8"))
                self.assertTrue(saved["configured"])
                self.assertNotIn("sk-test-1234567890", saved["masked_key"])
                self.assertIn("DEEPSEEK_API_KEY=sk-test-1234567890", env_path.read_text(encoding="utf-8"))
                with patch("apollo_claw.server._deepseek_settings_path", return_value=env_path):
                    request = urllib.request.Request(base + "/api/settings/deepseek/clear", data=b"{}", method="POST", headers=headers)
                    with urllib.request.urlopen(request, timeout=5) as response:
                        cleared = json.loads(response.read().decode("utf-8"))
                self.assertFalse(cleared["configured"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
                if old_key is not None:
                    os.environ["DEEPSEEK_API_KEY"] = old_key
                else:
                    os.environ.pop("DEEPSEEK_API_KEY", None)
