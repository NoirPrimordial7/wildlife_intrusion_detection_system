from __future__ import annotations

from typing import Any

from app.utils.paths import FIREBASE_CONFIG_EXAMPLE_PATH, FIREBASE_CONFIG_PATH, load_json


class NotificationService:
    def __init__(self) -> None:
        self.firebase_config_path = FIREBASE_CONFIG_PATH

    def send_local_alert(self, title: str, message: str) -> str:
        line = f"[LOCAL ALERT] {title}: {message}"
        print(line)
        return line

    def send_fcm_notification(self, title: str, body: str, data: dict[str, Any] | None = None) -> str:
        config_path = self.firebase_config_path if self.firebase_config_path.exists() else FIREBASE_CONFIG_EXAMPLE_PATH
        config = load_json(config_path, {})
        if not isinstance(config, dict) or not config.get("enabled"):
            return "Firebase disabled. Local alert only."

        project_id = config.get("project_id")
        service_account = config.get("service_account_json")
        topic = config.get("topic", "wildlife_alerts")
        if not project_id or not service_account:
            return "Firebase config incomplete. Local alert only."

        # Firebase Admin SDK wiring can be added here without changing alert_service.
        print(f"[FCM PLACEHOLDER] topic={topic} title={title} body={body} data={data or {}}")
        return "Firebase placeholder executed. Local alert only."

