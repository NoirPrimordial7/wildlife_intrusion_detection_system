"""Install once in a local virtual environment, then launch the desktop app."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent


def run(args):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description="Set up and run VanRakshak.")
    parser.add_argument("--setup-only", action="store_true", help="Install dependencies without opening the app.")
    parser.add_argument("--verify", action="store_true", help="Check the environment and model after setup.")
    args = parser.parse_args()
    if not (3, 10) <= sys.version_info[:2] <= (3, 12):
        raise RuntimeError("Install 64-bit Python 3.12 (or 3.10/3.11), then run START.bat again.")
    os.chdir(ROOT)
    environment = ROOT / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        print("[1/3] Creating a local Python environment...", flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    fingerprint = hashlib.sha256((ROOT / "requirements.txt").read_bytes()).hexdigest()
    marker = environment / ".requirements-installed"
    if not marker.exists() or marker.read_text() != fingerprint:
        print("[2/3] Installing packages. First setup may take several minutes...", flush=True)
        run([python, "-m", "pip", "install", "--upgrade", "pip"])
        run([python, "-m", "pip", "install", "-r", ROOT / "requirements.txt"])
        marker.write_text(fingerprint)
    if not (ROOT / "yolov8n.pt").exists():
        print("[3/3] Preparing YOLO weights (internet needed once)...", flush=True)
        run([python, "-c", "from ultralytics import YOLO; YOLO('yolov8n.pt')"])
    if args.verify:
        run([python, "scripts/check_environment.py"])
        run([python, "scripts/test_model.py"])
    if not args.setup_only:
        print("Opening VanRakshak. Use Guided demo or upload your own media.", flush=True)
        run([python, "app/main.py"])


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, OSError) as exc:
        print(f"\nSetup/start failed: {exc}\nFix the error above and run START.bat again.", file=sys.stderr)
        raise SystemExit(1)
