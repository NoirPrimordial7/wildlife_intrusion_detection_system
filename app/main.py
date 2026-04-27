from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ui.dashboard import run_dashboard
from app.ui.theme import apply_theme
from app.utils.logging_utils import get_logger
from app.utils.paths import ensure_project_dirs


def main() -> None:
    ensure_project_dirs()
    get_logger("wildlife.system", "system.log").info("System start")
    apply_theme()
    run_dashboard()


if __name__ == "__main__":
    main()
