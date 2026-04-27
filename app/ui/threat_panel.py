from __future__ import annotations

from typing import Any

import customtkinter as ctk

from app.ui.theme import COLORS, threat_color


class ThreatPanel(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(master, fg_color="transparent")
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        self.threat_card = self._card(0, "Threat Status")
        self.threat_value = ctk.CTkLabel(
            self.threat_card,
            text="SAFE",
            text_color=COLORS["safe"],
            font=ctk.CTkFont(size=32, weight="bold"),
        )
        self.threat_value.grid(row=1, column=0, sticky="w", padx=16, pady=(4, 0))
        self.reason_label = ctk.CTkLabel(
            self.threat_card,
            text="No dangerous animal detected",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=12),
            wraplength=300,
            justify="left",
        )
        self.reason_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))
        self.repeat_label = self._line(self.threat_card, 3, "Detection count: 0/3")

        self.detection_card = self._card(1, "Current Detection")
        self.animal_label = self._line(self.detection_card, 1, "Animal: --")
        self.confidence_label = self._line(self.detection_card, 2, "Confidence: --")
        self.yolo_label = self._line(self.detection_card, 3, "YOLO: --")
        self.classifier_label = self._line(self.detection_card, 4, "Classifier: --")
        self.processing_label = self._line(self.detection_card, 5, "Processing: --")
        self.mode_label = self._line(self.detection_card, 6, "Detection Mode: Hybrid YOLO + Classifier")

        self.camera_card = self._card(2, "Camera Info")
        self.camera_id_label = self._line(self.camera_card, 1, "Camera ID: CAM_01")
        self.location_label = self._line(self.camera_card, 2, "Location: Village Border Camera")
        self.source_label = self._line(self.camera_card, 3, "Source: idle")

        self.sms_card = self._card(3, "Phone Notification")
        self.sms_enabled_label = self._line(self.sms_card, 1, "SMS Status: Disabled")
        self.sms_provider_label = self._line(self.sms_card, 2, "SMS Provider: Twilio")
        self.sms_users_label = self._line(self.sms_card, 3, "Registered users: 0")
        self.sms_last_label = self._line(self.sms_card, 4, "Last notification: --")
        self.sms_hint_label = self._line(self.sms_card, 5, "Open SMS Settings from Video Evidence")

    def _card(self, row: int, title: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=8)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        frame.grid_columnconfigure(0, weight=1)
        label = ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        label.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        return frame

    def _line(self, parent: ctk.CTkFrame, row: int, text: str) -> ctk.CTkLabel:
        label = ctk.CTkLabel(
            parent,
            text=text,
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=13),
            anchor="w",
            justify="left",
            wraplength=310,
        )
        label.grid(row=row, column=0, sticky="ew", padx=16, pady=(2, 12 if row >= 8 else 2))
        return label

    def update_threat(self, level: str, reason: str, repeat_count: int | None = None, required_count: int | None = None) -> None:
        level = (level or "SAFE").upper()
        self.threat_value.configure(text=level, text_color=threat_color(level))
        self.reason_label.configure(text=reason or "")
        if repeat_count is not None and required_count is not None:
            self.repeat_label.configure(text=f"Detection count: {repeat_count}/{required_count}")

    def update_detection(self, prediction: dict[str, Any]) -> None:
        animal = prediction.get("display_label", prediction.get("label", "--"))
        confidence = float(prediction.get("confidence", 0.0))
        self.animal_label.configure(text=f"Animal: {animal}")
        self.confidence_label.configure(text=f"Confidence: {confidence:.1%}")
        primary = self._primary_detection(prediction)
        if primary:
            self.yolo_label.configure(text=f"YOLO: {primary.get('yolo_label', '--')} {float(primary.get('yolo_confidence', 0.0)):.1%}")
            self.classifier_label.configure(
                text=f"Classifier: {primary.get('normalized_classifier_label', '--')} {float(primary.get('classifier_confidence', 0.0)):.1%}"
            )
        else:
            self.yolo_label.configure(text="YOLO: --")
            raw = prediction.get("normalized_classifier_label", "--")
            self.classifier_label.configure(text=f"Classifier: {raw}")
        self.processing_label.configure(text=f"Processing: {float(prediction.get('processing_time_ms', 0.0)):.0f} ms")

    def _primary_detection(self, prediction: dict[str, Any]) -> dict[str, Any]:
        detections = prediction.get("detections")
        if isinstance(detections, list) and detections:
            valid = [item for item in detections if isinstance(item, dict)]
            dangerous = [item for item in valid if item.get("is_dangerous")]
            return max(dangerous or valid, key=lambda item: float(item.get("final_confidence", 0.0) or 0.0))
        return {}

    def update_camera_info(self, config: dict[str, Any], source_type: str, source_path: str = "") -> None:
        self.camera_id_label.configure(text=f"Camera ID: {config.get('camera_id', 'CAM_01')}")
        self.location_label.configure(text=f"Location: {config.get('camera_location', 'Village Border Camera')}")
        source_text = source_type
        if source_path:
            source_text = f"{source_type}: {source_path}"
        self.source_label.configure(text=f"Source: {source_text or 'idle'}")

    def update_sms_status(self, status: dict[str, Any]) -> None:
        enabled = "Enabled" if status.get("enabled") else "Disabled"
        provider = str(status.get("provider", "twilio")).replace("_", " ").title()
        self.sms_enabled_label.configure(text=f"SMS Status: {enabled}")
        self.sms_provider_label.configure(text=f"SMS Provider: {provider}")
        self.sms_users_label.configure(text=f"Registered users: {status.get('registered_users_count', 0)}")
        last = str(status.get("last_status", "--"))
        error = status.get("last_error")
        suffix = f" ({error})" if error else ""
        self.sms_last_label.configure(text=f"Last notification: {last}{suffix}")
