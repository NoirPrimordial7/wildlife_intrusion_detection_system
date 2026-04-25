from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

import numpy as np

from app.core.notification_service import NotificationService
from app.core.snapshot_service import SnapshotService
from app.utils.paths import ALERT_CONFIG_PATH, ALERT_EVENTS_PATH, load_json, save_json
from app.utils.time_utils import iso_timestamp


DEFAULT_ALERT_CONFIG = {
    "dangerous_animals": [
        "Tiger",
        "Leopard",
        "Lion",
        "Bear",
        "Brown bear",
        "Polar bear",
        "Elephant",
        "boar",
        "Snake",
        "Crocodile",
        "Wolf",
        "Hyena",
        "Rhinoceros",
        "Hippopotamus",
    ],
    "confidence_threshold": 0.70,
    "alert_cooldown_seconds": 120,
    "required_repeated_detections": 3,
    "camera_id": "CAM_01",
    "camera_location": "Village Border Camera",
}


def _normalize_name(name: str) -> str:
    return " ".join(str(name).replace("_", " ").split()).casefold()


class AlertService:
    def __init__(
        self,
        snapshot_service: SnapshotService,
        notification_service: NotificationService,
    ) -> None:
        self.snapshot_service = snapshot_service
        self.notification_service = notification_service
        self.config_path = ALERT_CONFIG_PATH
        self.events_path = ALERT_EVENTS_PATH
        self._lock = threading.Lock()
        self._last_animal: str | None = None
        self._repeat_count = 0
        self._last_alert_time: datetime | None = None
        self.ensure_files()
        self.config = self.load_config()

    def ensure_files(self) -> None:
        if not self.config_path.exists():
            save_json(self.config_path, DEFAULT_ALERT_CONFIG)
        if not self.events_path.exists():
            save_json(self.events_path, [])

    def load_config(self) -> dict[str, Any]:
        loaded = load_json(self.config_path, {})
        config = DEFAULT_ALERT_CONFIG.copy()
        if isinstance(loaded, dict):
            config.update(loaded)
        return config

    def update_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self.config.update(updates)
            self.config["confidence_threshold"] = float(self.config["confidence_threshold"])
            self.config["alert_cooldown_seconds"] = int(self.config["alert_cooldown_seconds"])
            self.config["required_repeated_detections"] = int(self.config["required_repeated_detections"])
            save_json(self.config_path, self.config)
            return self.config.copy()

    def load_events(self) -> list[dict[str, Any]]:
        events = load_json(self.events_path, [])
        return events if isinstance(events, list) else []

    def recent_events(self, limit: int = 8) -> list[dict[str, Any]]:
        return list(reversed(self.load_events()[-limit:]))

    def is_dangerous(self, animal: str) -> bool:
        dangerous = {_normalize_name(name) for name in self.config.get("dangerous_animals", [])}
        return _normalize_name(animal) in dangerous

    def evaluate_detection(
        self,
        prediction: dict[str, Any],
        frame: np.ndarray | None,
        source_type: str,
        source_path: str = "",
    ) -> dict[str, Any]:
        label = str(prediction.get("label", "Unknown"))
        confidence = float(prediction.get("confidence", 0.0))

        with self._lock:
            if not self.is_dangerous(label):
                self._last_animal = None
                self._repeat_count = 0
                return {
                    "threat_level": "SAFE",
                    "alert_triggered": False,
                    "reason": "No dangerous animal detected",
                    "repeat_count": 0,
                    "event": None,
                }

            threshold = float(self.config.get("confidence_threshold", 0.70))
            required = max(1, int(self.config.get("required_repeated_detections", 3)))
            cooldown = max(0, int(self.config.get("alert_cooldown_seconds", 120)))

            if confidence < threshold:
                self._last_animal = label
                self._repeat_count = 0
                return {
                    "threat_level": "WARNING",
                    "alert_triggered": False,
                    "reason": f"Dangerous animal below confidence threshold ({confidence:.0%} < {threshold:.0%})",
                    "repeat_count": 0,
                    "event": None,
                }

            if _normalize_name(label) == _normalize_name(self._last_animal or ""):
                self._repeat_count += 1
            else:
                self._last_animal = label
                self._repeat_count = 1

            if self._repeat_count < required:
                return {
                    "threat_level": "WARNING",
                    "alert_triggered": False,
                    "reason": f"Dangerous animal detected {self._repeat_count}/{required} times",
                    "repeat_count": self._repeat_count,
                    "event": None,
                }

            now = datetime.now().astimezone()
            if self._last_alert_time is not None:
                elapsed = (now - self._last_alert_time).total_seconds()
                if elapsed < cooldown:
                    remaining = int(cooldown - elapsed)
                    return {
                        "threat_level": "WARNING",
                        "alert_triggered": False,
                        "reason": f"Alert cooldown active ({remaining}s remaining)",
                        "repeat_count": self._repeat_count,
                        "event": None,
                    }

            snapshot_path = self.snapshot_service.save_snapshot(frame, label, confidence, source_type) if frame is not None else ""
            title = f"DANGER: {label} detected"
            message = f"{label} detected at {self.config.get('camera_location', 'camera')} with {confidence:.0%} confidence."
            self.notification_service.send_local_alert(title, message)
            fcm_status = self.notification_service.send_fcm_notification(
                title,
                message,
                {
                    "animal": label,
                    "confidence": f"{confidence:.4f}",
                    "source_type": source_type,
                },
            )
            notification_sent = not fcm_status.startswith("Firebase disabled") and not fcm_status.startswith("Firebase config incomplete")

            event = {
                "timestamp": iso_timestamp(),
                "camera_id": self.config.get("camera_id", "CAM_01"),
                "camera_location": self.config.get("camera_location", "Village Border Camera"),
                "animal": label,
                "confidence": confidence,
                "threat_level": "DANGER",
                "snapshot_path": snapshot_path,
                "notification_sent": notification_sent,
                "source_type": source_type,
                "source_path": source_path,
                "reason": "Dangerous animal confirmed",
            }
            events = self.load_events()
            events.append(event)
            save_json(self.events_path, events)

            self._last_alert_time = now
            self._repeat_count = 0
            return {
                "threat_level": "DANGER",
                "alert_triggered": True,
                "reason": "Dangerous animal confirmed",
                "repeat_count": required,
                "event": event,
            }

