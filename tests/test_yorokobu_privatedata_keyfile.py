"""privatedata._conn: the key can come from a file (XSERVER_SSH_KEY_FILE) for a local run; without any key it still does nothing."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sites.yorokobu import privatedata


class KeyFile(unittest.TestCase):
    def test_key_from_file(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "k"
            f.write_text("KEYTEXT", encoding="utf-8")
            env = {"XSERVER_SSH_KEY": "", "XSERVER_SSH_KEY_FILE": str(f), "XSERVER_HOST": "h", "XSERVER_USER": "u"}
            with mock.patch.dict(os.environ, env, clear=False):
                self.assertEqual(privatedata._conn(), ("KEYTEXT", "h", "u"))

    def test_no_key_does_nothing(self):
        env = {"XSERVER_SSH_KEY": "", "XSERVER_SSH_KEY_FILE": "", "XSERVER_HOST": "h", "XSERVER_USER": "u"}
        with mock.patch.dict(os.environ, env, clear=False):
            self.assertIsNone(privatedata._conn())

    def test_secret_still_wins(self):
        env = {"XSERVER_SSH_KEY": "SECRET", "XSERVER_SSH_KEY_FILE": "", "XSERVER_HOST": "h", "XSERVER_USER": "u"}
        with mock.patch.dict(os.environ, env, clear=False):
            self.assertEqual(privatedata._conn(), ("SECRET", "h", "u"))


if __name__ == "__main__":
    unittest.main()
