import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import os

import launch


class Launcher(unittest.TestCase):
    def setUp(self):
        self.previous_directory = Path.cwd()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(os.chdir, self.previous_directory)
        self.root = Path(self.temp.name)
        environment = self.root / ".venv" / ("Scripts" if os.name == "nt" else "bin")
        environment.mkdir(parents=True)
        (environment / ("python.exe" if os.name == "nt" else "python")).touch()
        (self.root / "requirements.txt").write_text("dummy-package==1\n")
        (self.root / "yolov8n.pt").touch()

    def mark_installed(self):
        fingerprint = hashlib.sha256((self.root / "requirements.txt").read_bytes()).hexdigest()
        (self.root / ".venv/.requirements-installed").write_text(fingerprint)

    def test_cached_start_skips_install_and_opens_app(self):
        self.mark_installed()
        with patch.object(launch, "ROOT", self.root), patch.object(launch, "run") as run, patch("sys.argv", ["launch.py"]):
            launch.main()
        self.assertEqual(len(run.call_args_list), 1)
        self.assertEqual(run.call_args.args[0][-1], "app/main.py")

    def test_failed_install_does_not_mark_environment_ready(self):
        with patch.object(launch, "ROOT", self.root), patch.object(launch, "run", side_effect=subprocess.CalledProcessError(1, "pip")), patch("sys.argv", ["launch.py"]):
            with self.assertRaises(subprocess.CalledProcessError):
                launch.main()
        self.assertFalse((self.root / ".venv/.requirements-installed").exists())

    def test_verification_mode_does_not_open_app(self):
        self.mark_installed()
        with patch.object(launch, "ROOT", self.root), patch.object(launch, "run") as run, patch("sys.argv", ["launch.py", "--setup-only", "--verify"]):
            launch.main()
        commands = [call.args[0][-1] for call in run.call_args_list]
        self.assertEqual(commands, ["scripts/check_environment.py", "scripts/test_model.py"])
