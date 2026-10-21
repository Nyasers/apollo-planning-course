import unittest
from pathlib import Path


class WindowsSetupEncodingTest(unittest.TestCase):
    def test_batch_launcher_is_ascii_and_uses_windows_powershell(self):
        path = Path(__file__).resolve().parents[1] / "\u4e00\u952e\u914d\u7f6eHarness.cmd"
        raw = path.read_bytes()
        self.assertTrue(all(byte < 128 for byte in raw))
        text = raw.decode("ascii")
        self.assertIn("chcp 65001", text)
        self.assertIn(r"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe", text)
        self.assertIn("-NoProfile -ExecutionPolicy Bypass", text)
        self.assertIn("--check", text)
        self.assertIn(b"\r\n", raw)
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))

    def test_oneclick_script_has_bom_and_check_only_mode(self):
        path = Path(__file__).resolve().parents[1] / "scripts" / "install-harness-oneclick.ps1"
        raw = path.read_bytes()
        self.assertEqual(raw[:3], b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
        self.assertIn("[switch]$CheckOnly", text)
        self.assertIn("@versionArgs", text)
        self.assertIn("Preflight checks passed", text)


if __name__ == "__main__":
    unittest.main()
