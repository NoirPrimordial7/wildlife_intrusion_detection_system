from __future__ import annotations

import json
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parent

MODELS_DIR = PROJECT_ROOT / "models"
DATA_DIR = PROJECT_ROOT / "data"
ASSETS_DIR = PROJECT_ROOT / "assets"
LOGS_DIR = PROJECT_ROOT / "logs"
DOCS_DIR = PROJECT_ROOT / "docs"
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
ALERT_EVENTS_PATH = DATA_DIR / "alert_events.json"
API_CONFIG_PATH = DATA_DIR / "api_config.json"
SYSTEM_CONFIG_PATH = DATA_DIR / "system_config.json"
REGISTERED_USERS_PATH = DATA_DIR / "registered_users.json"
NOTIFICATION_LOG_PATH = DATA_DIR / "notification_log.json"
SMS_CONFIG_EXAMPLE_PATH = DATA_DIR / "sms_config.example.json"
SMS_CONFIG_PATH = DATA_DIR / "sms_config.json"
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
