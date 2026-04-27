from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

from app.core.clip_service import ClipService
from app.core.detection_localizer import estimate_detection_region
from app.core.label_normalizer import normalize_key, normalize_label
from app.core.notification_service import NotificationService
from app.core.siren_service import SirenService
from app.core.snapshot_service import SnapshotService
from app.utils.logging_utils import get_logger
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
    "message_template": "DANGER: {animal} spotted near {camera_location}. Confidence: {confidence}%. Time: {timestamp}. Move domestic animals to safety and stay indoors.",
}


@dataclass
class CameraAlertState:
    last_animal: str | None = None
    repeat_count: int = 0
    last_alert_time: datetime | None = None


def _normalize_name(name: str) -> str:
    return normalize_key(name)


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
        self.logger = get_logger("wildlife.alerts", "alert.log")
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
        candidate = self._primary_detection(prediction)
        label = normalize_label(str(candidate.get("display_label", candidate.get("final_label", candidate.get("label", prediction.get("label", "Unknown"))))))
        final_label = normalize_label(str(candidate.get("final_label", label)))
        confidence = float(candidate.get("final_confidence", candidate.get("confidence", prediction.get("confidence", 0.0))))
        prediction_for_snapshot = dict(prediction)
        if candidate.get("bbox"):
            prediction_for_snapshot["bbox"] = candidate["bbox"]
        camera_id = camera_id or str(self.config.get("camera_id", "CAM_01"))
        camera_location = camera_location or str(self.config.get("camera_location", "Village Border Camera"))

        def finish(decision: dict[str, Any]) -> dict[str, Any]:
            decision["alert_decision_time_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
            if decision.get("event"):
                decision["event"]["alert_decision_time_ms"] = decision["alert_decision_time_ms"]
            return decision

        with self._lock:
            state = self._states.setdefault(camera_id, CameraAlertState())
            animal_severity = self.severity_for_animal(final_label)
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

            if _normalize_name(final_label) == _normalize_name(state.last_animal or ""):
                state.repeat_count += 1
            else:
                state.last_animal = final_label
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
            message = self._message_from_template(label, confidence, camera_location, timestamp, detection_metadata)
            snapshot_path = self.snapshot_service.save_snapshot(frame, label, confidence, source_type, prediction_for_snapshot) if frame is not None else ""
            clip_path = ""
            if self.clip_service is not None and frame is not None:
                clip_path = self.clip_service.start_alert_clip(camera_id, label, confidence, source_type)

            detection_region = estimate_detection_region(frame, prediction_for_snapshot) if frame is not None else {}
            siren_status = self.siren_service.trigger(severity) if self.siren_service is not None else "Siren unavailable."

            event = {
                "timestamp": timestamp,
                "camera_id": camera_id,
                "camera_location": camera_location,
                "animal": label,
                "display_label": label,
                "final_label": final_label,
                "raw_classifier_label": candidate.get("raw_classifier_label", prediction.get("raw_classifier_label", "")),
                "normalized_classifier_label": candidate.get("normalized_classifier_label", prediction.get("normalized_classifier_label", "")),
                "yolo_label": candidate.get("yolo_label", ""),
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
                "message": message,
                "processing_time_ms": float(detection_metadata.get("processing_time_ms", 0.0) or 0.0),
                "detection_video_timestamp": str(detection_metadata.get("detection_video_timestamp", "")),
                "detection_frame_number": int(detection_metadata.get("detection_frame_number", detection_metadata.get("frame_index", 0)) or 0),
                "playback_fps": float(detection_metadata.get("playback_fps", 0.0) or 0.0),
                "detection_region": detection_region,
                "location_note": detection_region.get("note", "Location: detected in current frame. Bounding box requires detection model."),
                "detections": prediction.get("detections", []),
                "siren_status": siren_status,
            }

            notification_results = self.notification_service.send_alert_to_registered_users(event)
            event["notification_results"] = notification_results
            event["notification_status"] = self._notification_summary(notification_results)
            event["notification_summary"] = self._notification_message(notification_results)
            event["notification_sent"] = bool(notification_results)
            event["last_sms_time"] = self._last_sms_time(notification_results)
            event["cooldown_remaining"] = int(self.config.get("alert_cooldown_seconds", 120))

            events = self.load_events()
            events.append(event)
            save_json(self.events_path, events)
            self.logger.warning(
                "Alert triggered: animal=%s confidence=%.3f camera=%s severity=%s snapshot=%s",
                label,
                confidence,
                camera_id,
                severity,
                snapshot_path,
            )

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

    def _last_sms_time(self, results: list[dict[str, Any]]) -> str:
        sent = [row for row in results if row.get("status") == "sent"]
        if sent:
            return str(sent[-1].get("timestamp", "--"))
        return "--"

    def _primary_detection(self, prediction: dict[str, Any]) -> dict[str, Any]:
        detections = prediction.get("detections")
        if isinstance(detections, list) and detections:
            normalized_dangerous = {_normalize_name(name) for name in self.config.get("dangerous_animals", [])}
            valid = [item for item in detections if isinstance(item, dict)]
            dangerous = [item for item in valid if _normalize_name(str(item.get("final_label", item.get("display_label", "")))) in normalized_dangerous]
            candidates = dangerous or valid
            if candidates:
                return max(candidates, key=lambda item: float(item.get("final_confidence", 0.0) or 0.0))
        return prediction

    def cooldown_remaining(self, camera_id: str | None = None) -> int:
        camera_id = camera_id or str(self.config.get("camera_id", "CAM_01"))
        state = self._states.get(camera_id)
        if not state or state.last_alert_time is None:
            return 0
        cooldown = max(0, int(self.config.get("alert_cooldown_seconds", 120)))
        elapsed = (datetime.now().astimezone() - state.last_alert_time).total_seconds()
        return max(0, int(cooldown - elapsed))

    def _message_from_template(
        self,
        animal: str,
        confidence: float,
        camera_location: str,
        timestamp: str,
        detection_metadata: dict[str, Any],
    ) -> str:
        template = str(self.config.get("message_template", DEFAULT_ALERT_CONFIG["message_template"]))
        video_time = str(detection_metadata.get("detection_video_timestamp", ""))
        return template.format(
            animal=animal,
            camera_location=camera_location,
            confidence=round(confidence * 100),
            timestamp=video_time or timestamp,
        )
