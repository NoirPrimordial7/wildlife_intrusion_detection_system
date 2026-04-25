from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.utils.paths import ANIMAL_INFO_PATH, CLASS_NAMES_PATH, MODEL_PATH


def check(name: str, fn) -> bool:
    try:
        detail = fn()
        print(f"[OK] {name}: {detail}")
        return True
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        return False


def check_python() -> str:
    version = sys.version_info
    if version[:2] != (3, 10):
        raise RuntimeError(f"Python 3.10 required, found {sys.version.split()[0]}")
    return sys.version.split()[0]


def check_tensorflow() -> str:
    import tensorflow as tf

    return tf.__version__


def check_opencv() -> str:
    import cv2

    return cv2.__version__


def check_tkinter() -> str:
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    root.update_idletasks()
    root.destroy()
    return "root create/destroy succeeded"


def check_customtkinter() -> str:
    import customtkinter as ctk

    return getattr(ctk, "__version__", "installed")


def require_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    return f"{path.relative_to(PROJECT_ROOT)} ({path.stat().st_size} bytes)"


def main() -> int:
    checks = [
        ("Python", check_python),
        ("TensorFlow import", check_tensorflow),
        ("OpenCV import", check_opencv),
        ("Tkinter", check_tkinter),
        ("CustomTkinter import", check_customtkinter),
        ("Model file", lambda: require_file(MODEL_PATH)),
        ("class_names.json", lambda: require_file(CLASS_NAMES_PATH)),
        ("animal_info.json", lambda: require_file(ANIMAL_INFO_PATH)),
    ]
    ok = True
    for name, fn in checks:
        ok = check(name, fn) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
