from __future__ import annotations

import os
import subprocess
import sys
import tkinter.messagebox as messagebox
from pathlib import Path


def main() -> None:
    base_dir = Path(sys.executable).resolve().parent
    pythonw = base_dir / "runtime" / "pythonw.exe"
    app_main = base_dir / "app" / "main.py"

    if not pythonw.exists():
        messagebox.showerror("Wildlife Alert System", f"Bundled runtime not found:\n{pythonw}")
        return
    if not app_main.exists():
        messagebox.showerror("Wildlife Alert System", f"Application entry point not found:\n{app_main}")
        return

    env = os.environ.copy()
    runtime_site_packages = base_dir / "runtime" / "Lib" / "site-packages"
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(base_dir),
            str(runtime_site_packages),
            env.get("PYTHONPATH", ""),
        ]
    )
    env["PYTHONNOUSERSITE"] = "1"

    subprocess.Popen(
        [str(pythonw), str(app_main)],
        cwd=str(base_dir),
        env=env,
        close_fds=True,
    )


if __name__ == "__main__":
    main()
