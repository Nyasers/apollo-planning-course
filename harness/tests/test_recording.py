import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apollo_claw.config import Settings
from apollo_claw.experiment import ExperimentStore
from apollo_claw.recording import elapsed_seconds, is_active, start_recording


class RecordingSessionTest(unittest.TestCase):
    def test_dry_run_creates_preview_without_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(Path(tmp))
            experiment = store.create("crosswalk", "人行道避让")
            record = start_recording(
                Settings(output_dir=tmp),
                store,
                experiment,
                tag="crosswalk",
                execute=False,
            )
            self.assertEqual(record["status"], "dry-run")
            self.assertIn("cyber_recorder", record["command_preview"])
            self.assertFalse(is_active(record))

    def test_paused_time_is_not_counted(self):
        now = datetime.now(timezone.utc)
        record = {
            "status": "paused",
            "elapsed_sec": 12,
            "session": {
                "active": True,
                "phase": "paused",
                "resumed_at": "",
                "paused_at": now.isoformat(),
            },
        }
        self.assertTrue(is_active(record))
        self.assertEqual(elapsed_seconds(record, now + timedelta(seconds=30)), 12)


if __name__ == "__main__":
    unittest.main()