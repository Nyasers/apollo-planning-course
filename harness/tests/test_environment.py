import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from apollo_claw.config import Settings
from apollo_claw.environment import probe_runtime, wsl_distribution


class EnvironmentProbeTest(unittest.TestCase):
    def test_wsl_distribution_parses_utf16_list_output(self):
        output = "  NAME            STATE           VERSION\n* Ubuntu-22.04    Running         2\n".encode("utf-16-le")
        completed = SimpleNamespace(stdout=output, stderr=b"", returncode=0)
        with patch("apollo_claw.environment.subprocess.run", return_value=completed):
            result = wsl_distribution(Settings())
        self.assertTrue(result["running"])
        self.assertEqual(result["distro"], "Ubuntu-22.04")
        self.assertEqual(result["version"], "2")

    @unittest.skipUnless(os.name == "nt", "Windows-only WSL path mapping")
    def test_windows_workspace_defaults_to_wsl_unc(self):
        result = Settings()
        self.assertTrue(result.apollo_workspace_host.startswith(r"\\wsl.localhost"))
        self.assertIn("application-pnc", result.apollo_workspace_host)

    def test_probe_keeps_layers_separate(self):
        linux = {"installed": True, "running": True, "state": "Running", "distro": "Ubuntu-22.04", "version": "2"}
        dreamview = {"ok": False, "url": "http://127.0.0.1:8888/", "error": "timed out"}
        probe = SimpleNamespace(ok=True, stdout="KERNEL=6.6\nUPTIME=12\nDOCKER_VERSION=29.7.1\nCONTAINER_STATE=exited\n", stderr="")
        with patch("apollo_claw.environment.wsl_distribution", return_value=linux), \
             patch("apollo_claw.environment.check_dreamview", return_value=dreamview), \
             patch("apollo_claw.environment.run_wsl", return_value=probe):
            result = probe_runtime(Settings())
        self.assertTrue(result["linux"]["running"])
        self.assertTrue(result["docker"]["started"])
        self.assertFalse(result["apollo"]["started"])
        self.assertFalse(result["simulation"]["started"])
        self.assertIn("Apollo", result["simulation"]["summary"])


if __name__ == "__main__":
    unittest.main()