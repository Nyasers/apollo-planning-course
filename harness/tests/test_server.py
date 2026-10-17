import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from apollo_claw.config import Settings
from apollo_claw.server import make_handler


class ServerTest(unittest.TestCase):
    def test_health_and_tasks_are_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            tasks = Path(tmp) / "tasks.json"
            tasks.write_text(json.dumps({"tasks": [{"id": "crosswalk", "title": "人行道避让"}]}), encoding="utf-8")
            settings = Settings(tasks_file=str(tasks), output_dir=tmp)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(settings))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urllib.request.urlopen(base + "/health", timeout=5) as response:
                    data = json.loads(response.read().decode("utf-8"))
                self.assertTrue(data["ok"])
                with urllib.request.urlopen(base + "/api/tasks", timeout=5) as response:
                    data = json.loads(response.read().decode("utf-8"))
                self.assertEqual(data["tasks"][0]["id"], "crosswalk")
                with urllib.request.urlopen(base + "/", timeout=5) as response:
                    page = response.read().decode("utf-8")
                self.assertIn("APOLLO CLAW", page)
                self.assertIn("task-list", page)
                self.assertIn('window.__APOLLO_CLAW_TOKEN__ = "', page)
                self.assertNotIn("__APC_TOKEN__", page)
                with urllib.request.urlopen(base + "/app.js", timeout=5) as response:
                    self.assertEqual(response.status, 200)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
