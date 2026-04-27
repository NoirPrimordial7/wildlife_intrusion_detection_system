from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def resource_path(relative_path: str | Path) -> str:
    """Return an absolute path for bundled read-only resources."""
    base_path = Path(getattr(sys, "_MEIPASS", Path.cwd()))
    return str(base_path / relative_path)


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _resource_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = _runtime_root()
RESOURCE_ROOT = _resource_root()


def _external_or_resource(relative_path: str) -> Path:
    external_path = PROJECT_ROOT / relative_path
    if external_path.exists():
        return external_path
    return RESOURCE_ROOT / relative_path


MODELS_DIR = _external_or_resource("models")
DATA_DIR = _external_or_resource("data")
ASSETS_DIR = _external_or_resource("assets")
LOGS_DIR = PROJECT_ROOT / "logs"
DOCS_DIR = _external_or_resource("docs")
ALERTS_DIR = ASSETS_DIR / "alerts"
SNAPSHOTS_DIR = ALERTS_DIR / "snapshots"
CLIPS_DIR = ALERTS_DIR / "clips"
REPORTS_DIR = ASSETS_DIR / "reports"
TEST_IMAGES_DIR = ASSETS_DIR / "test_images"
TEST_VIDEOS_DIR = ASSETS_DIR / "test_videos"
REFERENCE_IMAGES_DIR = ASSETS_DIR / "reference_images"

MODEL_PATH = MODELS_DIR / "animal_classification_model_final.h5"
CLASS_NAMES_PATH = DATA_DIR / "class_names.json"
ANIMAL_INFO_PATH = DATA_DIR / "animal_info.json"
ALERT_CONFIG_PATH = DATA_DIR / "alert_config.json"
DETECTION_CONFIG_PATH = DATA_DIR / "detection_config.json"
ALERT_EVENTS_PATH = PROJECT_ROOT / "data" / "alert_events.json"
API_CONFIG_PATH = DATA_DIR / "api_config.json"
SYSTEM_CONFIG_PATH = DATA_DIR / "system_config.json"
REGISTERED_USERS_PATH = PROJECT_ROOT / "data" / "registered_users.json"
NOTIFICATION_LOG_PATH = PROJECT_ROOT / "data" / "notification_log.json"
SMS_CONFIG_EXAMPLE_PATH = DATA_DIR / "sms_config.example.json"
SMS_CONFIG_PATH = PROJECT_ROOT / "data" / "sms_config.json"
FIREBASE_CONFIG_EXAMPLE_PATH = DATA_DIR / "firebase_config.example.json"
FIREBASE_CONFIG_PATH = DATA_DIR / "firebase_config.json"


def ensure_project_dirs() -> None:
    for path in (
        MODELS_DIR,
        DATA_DIR,
        ALERTS_DIR,
        SNAPSHOTS_DIR,
        CLIPS_DIR,
        REPORTS_DIR,
        TEST_IMAGES_DIR,
        TEST_VIDEOS_DIR,
        REFERENCE_IMAGES_DIR,
        LOGS_DIR,
        DOCS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def relative_to_project(path: str | Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(resolved)
