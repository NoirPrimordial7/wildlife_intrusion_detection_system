from __future__ import annotations

import argparse
import subprocess
import sys
import venv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    PROJECT_ROOT / "models" / "animal_classification_model_final.h5",
    PROJECT_ROOT / "data" / "class_names.json",
    PROJECT_ROOT / "data" / "animal_info.json",
    PROJECT_ROOT / "requirements.txt",
]


def print_status(label: str, ok: bool, detail: str = "") -> None:
    prefix = "[OK]" if ok else "[FAIL]"
    suffix = f": {detail}" if detail else ""
    print(f"{prefix} {label}{suffix}")


def check_files() -> bool:
    ok = True
    for path in REQUIRED_FILES:
        exists = path.exists()
        print_status(str(path.relative_to(PROJECT_ROOT)), exists)
        ok = ok and exists
    return ok


def check_python() -> bool:
    ok = sys.version_info[:2] == (3, 10)
    print_status("Python 3.10", ok, sys.version.split()[0])
    return ok


def create_venv() -> Path:
    venv_path = PROJECT_ROOT / ".venv"
    if not venv_path.exists():
        print(f"Creating virtual environment: {venv_path}")
        venv.EnvBuilder(with_pip=True).create(venv_path)
    else:
        print(f"Virtual environment already exists: {venv_path}")
    return venv_path


def install_requirements(venv_path: Path) -> None:
    python = venv_path / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
    subprocess.check_call([str(python), "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([str(python), "-m", "pip", "install", "-r", str(PROJECT_ROOT / "requirements.txt")])


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup/check helper for the wildlife alert project.")
    parser.add_argument("--create-venv", action="store_true", help="Create .venv if it does not exist.")
    parser.add_argument("--install", action="store_true", help="Install requirements into .venv.")
    args = parser.parse_args()

    ok = check_python() and check_files()
    if args.create_venv or args.install:
        venv_path = create_venv()
        if args.install:
            install_requirements(venv_path)

    print("")
    print("Launch command after setup:")
    print("python app/main.py")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
