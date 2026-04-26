from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

from app.core.clip_service import ClipService
from app.core.detection_localizer import estimate_detection_region
from app.core.notification_service import NotificationService
from app.core.siren_service import SirenService
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
        "Wolf",
        "Hyena",
        "Crocodile",
        "Snake",
        "boar",
        "Rhinoceros",
        "Hippopotamus",
    ],
    "severity_mapping": {
        "Tiger": "CRITICAL",
        "Leopard": "CRITICAL",
        "Lion": "CRITICAL",
        "Bear": "HIGH",
        "Brown bear": "HIGH",
        "Polar bear": "HIGH",
        "Elephant": "HIGH",
        "Wolf": "HIGH",
        "Hyena": "HIGH",
        "Crocodile": "HIGH",
        "Rhinoceros": "HIGH",
        "Hippopotamus": "HIGH",
        "Snake": "WARNING",
        "boar": "WARNING",
    },
    "confidence_threshold": 0.70,
    "alert_cooldown_seconds": 120,
    "required_repeated_detections": 3,
    "camera_id": "CAM_01",
    "camera_location": "Village Border Camera",
    "siren_enabled": True,
}


@dataclass
class CameraAlertState:
    last_animal: str | None = None
    repeat_count: int = 0
    last_alert_time: datetime | None = None


def _normalize_name(name: str) -> str:
    return " ".join(str(name).replace("_", " ").split()).casefold()


class AlertService:
    def __init__(
        self,
        snapshot_service: SnapshotService,
        notification_service: NotificationService,
        clip_service: ClipService | None = None,
        siren_service: SirenService | None = None,
    ) -> None:
        self.snapshot_service = snapshot_service
        self.notification_service = notification_service
        self.clip_service = clip_service
        self.siren_service = siren_service
        self.config_path = ALERT_CONFIG_PATH
        self.events_path = ALERT_EVENTS_PATH
        self._lock = threading.Lock()
        self._states: dict[str, CameraAlertState] = {}
        self.ensure_files()
        self.config = self.load_config()
        if self.siren_service is not None:
            self.siren_service.set_enabled(bool(self.config.get("siren_enabled", True)))

    def ensure_files(self) -> None:
        if not self.config_path.exists():
            save_json(self.config_path, DEFAULT_ALERT_CONFIG)
        if not self.events_path.exists():
            save_json(self.events_path, [])

    def load_config(self) -> dict[str, Any]:
        loaded = load_json(self.config_path, {})
        config = DEFAULT_ALERT_CONFIG.copy()
        config["severity_mapping"] = DEFAULT_ALERT_CONFIG["severity_mapping"].copy()
        if isinstance(loaded, dict):
            severity_mapping = loaded.get("severity_mapping")
            config.update(loaded)
            if isinstance(severity_mapping, dict):
                merged = DEFAULT_ALERT_CONFIG["severity_mapping"].copy()
                merged.update(severity_mapping)
                config["severity_mapping"] = merged
        return config

    def update_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self.config.update(updates)
            self.config["confidence_threshold"] = float(self.config["confidence_threshold"])
            self.config["alert_cooldown_seconds"] = int(self.config["alert_cooldown_seconds"])
            self.config["required_repeated_detections"] = int(self.config["required_repeated_detections"])
            self.config["siren_enabled"] = bool(self.config.get("siren_enabled", True))
            save_json(self.config_path, self.config)
            if self.siren_service is not None:
                self.siren_service.set_enabled(self.config["siren_enabled"])
            return self.config.copy()

    def load_events(self) -> list[dict[str, Any]]:
        events = load_json(self.events_path, [])
        return events if isinstance(events, list) else []

    def recent_events(self, limit: int = 8) -> list[dict[str, Any]]:
        return list(reversed(self.load_events()[-limit:]))

    def is_dangerous(self, animal: str) -> bool:
        dangerous = {_normalize_name(name) for name in self.config.get("dangerous_animals", [])}
        return _normalize_name(animal) in dangerous

    def severity_for_animal(self, animal: str) -> str:
        if not self.is_dangerous(animal):
            return "LOW"
        mapping = self.config.get("severity_mapping", {})
        if isinstance(mapping, dict):
            normalized = _normalize_name(animal)
            for name, severity in mapping.items():
                if _normalize_name(name) == normalized:
                    return str(severity).upper()
        return "HIGH"

    def evaluate_detection(
        self,
        prediction: dict[str, Any],
        frame: np.ndarray | None,
        source_type: str,
        source_path: str = "",
        camera_id: str | None = None,
        camera_location: str | None = None,
        detection_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        detection_metadata = detection_metadata or {}
        label = str(prediction.get("label", "Unknown"))
        confidence = float(prediction.get("confidence", 0.0))
        camera_id = camera_id or str(self.config.get("camera_id", "CAM_01"))
        camera_location = camera_location or str(self.config.get("camera_location", "Village Border Camera"))

        def finish(decision: dict[str, Any]) -> dict[str, Any]:
            decision["alert_decision_time_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
            if decision.get("event"):
                decision["event"]["alert_decision_time_ms"] = decision["alert_decision_time_ms"]
            return decision

        with self._lock:
            state = self._states.setdefault(camera_id, CameraAlertState())
            animal_severity = self.severity_for_animal(label)
            if animal_severity == "LOW":
                state.last_animal = None
                state.repeat_count = 0
                return finish(
                    {
                        "threat_level": "LOW",
                        "severity": "LOW",
                        "alert_triggered": False,
                        "reason": "No dangerous animal detected",
                        "repeat_count": 0,
                        "event": None,
                    }
                )

            threshold = float(self.config.get("confidence_threshold", 0.70))
            required = max(1, int(self.config.get("required_repeated_detections", 3)))
            cooldown = max(0, int(self.config.get("alert_cooldown_seconds", 120)))

            if confidence < threshold:
                state.last_animal = label
                state.repeat_count = 0
                return finish(
                    {
                        "threat_level": "WARNING",
                        "severity": "WARNING",
                        "alert_triggered": False,
                        "reason": f"{label} below confidence threshold ({confidence:.0%} < {threshold:.0%})",
                        "repeat_count": 0,
                        "event": None,
                    }
                )

            if _normalize_name(label) == _normalize_name(state.last_animal or ""):
                state.repeat_count += 1
            else:
                state.last_animal = label
                state.repeat_count = 1

            if state.repeat_count < required:
                return finish(
                    {
                        "threat_level": "WARNING",
                        "severity": "WARNING",
                        "alert_triggered": False,
                        "reason": f"Dangerous animal detected {state.repeat_count}/{required} times",
                        "repeat_count": state.repeat_count,
                        "event": None,
                    }
                )

            now = datetime.now().astimezone()
            if state.last_alert_time is not None:
                elapsed = (now - state.last_alert_time).total_seconds()
                if elapsed < cooldown:
                    remaining = int(cooldown - elapsed)
                    return finish(
                        {
                            "threat_level": "WARNING",
                            "severity": "WARNING",
                            "alert_triggered": False,
                            "reason": f"Alert cooldown active ({remaining}s remaining)",
                            "repeat_count": state.repeat_count,
                            "event": None,
                        }
                    )

            severity = animal_severity
            timestamp = iso_timestamp()
            snapshot_path = self.snapshot_service.save_snapshot(frame, label, confidence, source_type) if frame is not None else ""
            clip_path = ""
            if self.clip_service is not None and frame is not None:
                clip_path = self.clip_service.start_alert_clip(camera_id, label, confidence, source_type)

            detection_region = estimate_detection_region(frame, prediction) if frame is not None else {}
            siren_status = self.siren_service.trigger(severity) if self.siren_service is not None else "Siren unavailable."

            event = {
                "timestamp": timestamp,
                "camera_id": camera_id,
                "camera_location": camera_location,
                "animal": label,
                "confidence": confidence,
                "threat_level": "DANGER",
                "severity": severity,
                "snapshot_path": snapshot_path,
                "clip_path": clip_path,
                "source_type": source_type,
                "source_path": source_path,
                "video_filename": str(source_path).replace("\\", "/").split("/")[-1],
                "ai_interval": str(detection_metadata.get("ai_interval", "")),
                "reason": "Dangerous animal confirmed",
                "processing_time_ms": float(detection_metadata.get("processing_time_ms", 0.0) or 0.0),
                "detection_video_timestamp": str(detection_metadata.get("detection_video_timestamp", "")),
                "detection_frame_number": int(detection_metadata.get("detection_frame_number", detection_metadata.get("frame_index", 0)) or 0),
                "playback_fps": float(detection_metadata.get("playback_fps", 0.0) or 0.0),
                "detection_region": detection_region,
                "location_note": detection_region.get("note", "Location: detected in current frame. Bounding box requires detection model."),
                "siren_status": siren_status,
            }

            notification_results = self.notification_service.send_alert_to_registered_users(event)
            event["notification_results"] = notification_results
            event["notification_status"] = self._notification_summary(notification_results)
            event["notification_summary"] = self._notification_message(notification_results)
            event["notification_sent"] = bool(notification_results)

            events = self.load_events()
            events.append(event)
            save_json(self.events_path, events)

            state.last_alert_time = now
            state.repeat_count = 0
            return finish(
                {
                    "threat_level": "DANGER",
                    "severity": severity,
                    "alert_triggered": True,
                    "reason": "Dangerous animal confirmed",
                    "repeat_count": required,
                    "event": event,
                }
            )

    def _notification_summary(self, results: list[dict[str, Any]]) -> str:
        if not results:
            return "no_registered_users"
        statuses = {str(result.get("status", "")) for result in results}
        if "sent" in statuses:
            return "sent"
        if "demo_sent" in statuses:
            return "demo_sent"
        if "failed" in statuses:
            return "failed"
        if "disabled" in statuses:
            return "disabled"
        return sorted(statuses)[0] if statuses else "unknown"

    def _notification_message(self, results: list[dict[str, Any]]) -> str:
        if not results:
            return "No enabled registered users."
        sent = sum(1 for result in results if result.get("status") == "sent")
        failed = [result for result in results if result.get("status") == "failed"]
        disabled = [result for result in results if result.get("status") == "disabled"]
        if sent:
            return f"SMS sent to {sent} users"
        if failed:
            return f"SMS failed: {failed[0].get('error', 'unknown error')}"
        if disabled:
            return "Real SMS disabled. Enable data/sms_config.json."
        return str(results[0].get("status", "unknown"))
