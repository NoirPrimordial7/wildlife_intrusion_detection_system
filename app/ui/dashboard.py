from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk

from app.core.alert_service import AlertService
from app.core.camera_service import CameraService
from app.core.clip_service import ClipService
from app.core.detection_localizer import draw_detection_overlay
from app.core.notification_service import NotificationService
from app.core.prediction_service import PredictionService
from app.core.report_service import ReportService
from app.core.siren_service import SirenService
from app.core.snapshot_service import SnapshotService
from app.core.video_service import VideoService
from app.ui.alert_history_panel import AlertHistoryPanel
from app.ui.camera_panel import CameraPanel
from app.ui.evidence_panel import EvidencePanel
from app.ui.settings_panel import SettingsPanel
from app.ui.sidebar import Sidebar
from app.ui.theme import COLORS
from app.ui.threat_panel import ThreatPanel
from app.utils.image_utils import load_image_as_bgr
from app.utils.paths import ALERTS_DIR, PROJECT_ROOT, ensure_project_dirs


class Dashboard(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ensure_project_dirs()

        self.title("Video Intrusion Detection - Wildlife Alert System")
        self.geometry("1480x860")
        self.minsize(1160, 720)
        self.configure(fg_color=COLORS["app_bg"])

        self.prediction_service = PredictionService()
        self.notification_service = NotificationService()
        self.snapshot_service = SnapshotService()
        self.clip_service = ClipService()
        self.siren_service = SirenService()
        self.alert_service = AlertService(
            self.snapshot_service,
            self.notification_service,
            self.clip_service,
            self.siren_service,
        )
        self.report_service = ReportService()

        self.camera_service = CameraService(
            self.prediction_service,
            self._on_frame_from_worker,
            self._on_prediction_from_worker,
            self._on_error_from_worker,
            self._on_camera_status_from_worker,
        )
        self.video_service = VideoService(
            self.prediction_service,
            self._on_frame_from_worker,
            self._on_prediction_from_worker,
            self._on_video_progress_from_worker,
            self._on_error_from_worker,
        )

        self._source_type = "idle"
        self._source_path = ""
        self._build_layout()
        self._refresh_static_state()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, minsize=240, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, minsize=410, weight=0)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(
            self,
            {
                "start_webcam": self.start_webcam_monitoring,
                "upload_image": self.upload_image,
                "upload_video": self.upload_video,
                "stop_monitoring": self.stop_monitoring,
                "export_report": self.export_report,
                "open_alerts": self.open_alerts_folder,
                "settings": self.focus_settings,
            },
        )
        self.sidebar.grid(row=0, column=0, sticky="nsw")

        self.camera_panel = CameraPanel(
            self,
            {
                "start": self.video_start,
                "pause": self.video_pause,
                "resume": self.video_resume,
                "stop": self.video_stop,
                "restart": self.video_restart,
                "backward": lambda: self.video_service.seek_seconds(-5),
                "forward": lambda: self.video_service.seek_seconds(5),
                "speed": self.video_service.set_speed,
                "interval": self.video_service.set_detection_interval,
                "seek_percent": self.video_service.seek_percent,
            },
        )
        self.camera_panel.grid(row=0, column=1, sticky="nsew")

        self.right_panel = ctk.CTkScrollableFrame(self, width=410, fg_color=COLORS["app_bg"], corner_radius=0)
        self.right_panel.grid(row=0, column=2, sticky="nsew", padx=(0, 14), pady=14)
        self.right_panel.grid_columnconfigure(0, weight=1)

        self.threat_panel = ThreatPanel(self.right_panel)
        self.threat_panel.grid(row=0, column=0, sticky="ew")

        self.evidence_panel = EvidencePanel(self.right_panel, self.open_project_file)
        self.evidence_panel.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self.alert_history_panel = AlertHistoryPanel(self.right_panel, self.open_project_file)
        self.alert_history_panel.grid(row=2, column=0, sticky="ew", pady=(0, 12))

        self.settings_panel = SettingsPanel(
            self.right_panel,
            self.alert_service.config,
            self.save_settings,
            self.stop_alarm,
            self.notification_service.load_registered_users(),
            self.save_registered_users,
            self.test_sms_user,
        )
        self.settings_panel.grid(row=3, column=0, sticky="ew")

    def _refresh_static_state(self) -> None:
        config = self.alert_service.config
        self.threat_panel.update_camera_info(config, self._source_type, self._source_path)
        self.threat_panel.update_sms_status(self.notification_service.sms_status())
        self._refresh_alert_views()
        self.camera_panel.set_status(
            animal="--",
            confidence=0.0,
            threat_level="LOW",
            ai_interval=self.video_service.interval_label,
            source_type="video",
            stream_state="Upload a video, then click Start Detection",
        )

    def upload_video(self) -> None:
        path = filedialog.askopenfilename(
            title="Select wildlife intrusion video",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.webm"), ("All files", "*.*")],
        )
        if not path:
            return
        self.stop_monitoring(reset_status=False)
        self._source_type = "video"
        self._source_path = path
        self.camera_panel.show_video_controls(True)
        self.camera_panel.set_status(
            animal="--",
            confidence=0.0,
            threat_level="LOW",
            ai_interval=self.video_service.interval_label,
            source_type="video",
            stream_state="Video loaded. Click Start Detection.",
        )
        self.camera_panel.set_metrics(0.0, 0.0, "--", 0.0)
        self.threat_panel.update_threat("LOW", "Video loaded. Waiting for Start Detection.")
        self.threat_panel.update_camera_info(self.alert_service.config, self._source_type, path)
        self.video_service.open_video(path)

    def video_start(self) -> None:
        self.camera_service.stop(wait=False)
        self.camera_panel.set_status(stream_state="Monitoring video for dangerous wildlife intrusion...")
        self.threat_panel.update_threat("LOW", "Monitoring video for dangerous wildlife intrusion...")
        self.video_service.start()

    def video_pause(self) -> None:
        self.video_service.pause()
        self.camera_panel.set_status(stream_state="Detection paused")

    def video_resume(self) -> None:
        self.camera_panel.set_status(stream_state="Monitoring video for dangerous wildlife intrusion...")
        self.video_service.resume()

    def video_stop(self) -> None:
        self.video_service.stop(wait=False, reset=True)
        self.clip_service.finalize_camera(self.alert_service.config.get("camera_id", "CAM_01"))
        self.camera_panel.set_status(threat_level="LOW", source_type="video", stream_state="Detection stopped")
        self.threat_panel.update_threat("LOW", "Detection stopped")

    def video_restart(self) -> None:
        self.camera_panel.set_status(stream_state="Monitoring video for dangerous wildlife intrusion...")
        self.video_service.restart()

    def start_webcam_monitoring(self) -> None:
        self.video_service.stop(wait=False, reset=False)
        self._source_type = "webcam"
        self._source_path = "camera:0"
        self.camera_panel.show_video_controls(False)
        self.camera_panel.set_status(
            animal="--",
            confidence=0.0,
            threat_level="LOW",
            ai_interval="Every 1 sec",
            source_type="webcam",
            stream_state="Starting webcam monitoring...",
        )
        self.camera_service.start(camera_index=0, prediction_interval_seconds=1.0)

    def upload_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Select wildlife image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.webp"), ("All files", "*.*")],
        )
        if not path:
            return
        self.stop_monitoring(reset_status=False)
        self._source_type = "image"
        self._source_path = path
        self.camera_panel.show_video_controls(False)
        try:
            frame = load_image_as_bgr(path)
        except Exception as exc:
            self._show_error(f"Image could not be loaded: {exc}")
            return
        self.camera_panel.set_frame(frame)
        self.camera_panel.set_status(
            animal="Predicting...",
            confidence=0.0,
            threat_level="LOW",
            ai_interval="Single image",
            source_type="image",
            stream_state="Analyzing image",
        )
        self.threat_panel.update_camera_info(self.alert_service.config, self._source_type, path)
        threading.Thread(target=self._predict_image_worker, args=(frame, path), daemon=True).start()

    def stop_monitoring(self, reset_status: bool = True) -> None:
        self.camera_service.stop(wait=False)
        self.video_service.stop(wait=False, reset=False)
        self.clip_service.finalize_all()
        if reset_status:
            self._source_type = "idle"
            self._source_path = ""
            self.camera_panel.set_status(threat_level="LOW", ai_interval=self.video_service.interval_label, source_type="idle", stream_state="Stopped")
            self.threat_panel.update_threat("LOW", "Monitoring stopped")
            self.threat_panel.update_camera_info(self.alert_service.config, "idle", "")

    def export_report(self) -> None:
        try:
            path = self.report_service.export_alert_report()
            messagebox.showinfo("Report exported", f"Report saved to:\n{path}")
        except Exception as exc:
            self._show_error(f"Report export failed: {exc}")

    def open_alerts_folder(self) -> None:
        ALERTS_DIR.mkdir(parents=True, exist_ok=True)
        self.open_project_file(ALERTS_DIR)

    def open_project_file(self, path: str | Path) -> None:
        target = Path(path)
        if not target.is_absolute():
            target = PROJECT_ROOT / target
        try:
            if os.name == "nt":
                os.startfile(str(target))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as exc:
            self._show_error(f"Could not open file: {exc}")

    def focus_settings(self) -> None:
        self.settings_panel.configure(border_width=2, border_color=COLORS["accent"])
        self.after(1200, lambda: self.settings_panel.configure(border_width=0))

    def save_settings(self, updates: dict[str, Any]) -> None:
        try:
            config = self.alert_service.update_config(updates)
            self.threat_panel.update_camera_info(config, self._source_type, self._source_path)
            messagebox.showinfo("Settings saved", "Alert settings updated.")
        except Exception as exc:
            self._show_error(f"Settings could not be saved: {exc}")

    def save_registered_users(self, users: list[dict[str, Any]]) -> None:
        try:
            self.notification_service.save_registered_users(users)
            self.threat_panel.update_sms_status(self.notification_service.sms_status())
            messagebox.showinfo("Registered users saved", "Phone notification users updated.")
        except Exception as exc:
            self._show_error(f"Registered users could not be saved: {exc}")

    def test_sms_user(self, user: dict[str, Any]) -> None:
        result = self.notification_service.send_test_sms(user)
        self.threat_panel.update_sms_status(self.notification_service.sms_status())
        status = result.get("status", "unknown")
        error = result.get("error")
        if status == "sent":
            messagebox.showinfo("Test SMS sent", f"SMS sent to {result.get('phone', '')}.")
        elif status == "disabled":
            messagebox.showwarning("SMS disabled", "Real SMS disabled. Enable data/sms_config.json.")
        else:
            messagebox.showerror("Test SMS failed", str(error or "Unknown SMS error"))

    def stop_alarm(self) -> None:
        self.siren_service.stop()

    def _predict_image_worker(self, frame: Any, path: str) -> None:
        try:
            started_at = time.perf_counter()
            prediction = self.prediction_service.predict_frame(frame.copy())
            processing_time_ms = round((time.perf_counter() - started_at) * 1000, 2)
            metadata = {
                "source_type": "image",
                "source_path": path,
                "ai_interval": "Single image",
                "processing_time_ms": processing_time_ms,
                "detection_video_timestamp": "--",
                "detection_frame_number": 0,
                "playback_fps": 0.0,
            }
            self._handle_prediction_background(prediction, frame.copy(), metadata)
        except Exception as exc:
            self._on_error_from_worker(f"Image prediction failed: {exc}")

    def _on_frame_from_worker(self, frame: Any, metadata: dict[str, Any]) -> None:
        camera_id = str(metadata.get("camera_id") or self.alert_service.config.get("camera_id", "CAM_01"))
        self.clip_service.add_frame(camera_id, frame, metadata)
        self.after(0, lambda: self._apply_frame(frame, metadata))

    def _apply_frame(self, frame: Any, metadata: dict[str, Any]) -> None:
        self.camera_panel.set_frame(frame)
        self._source_type = metadata.get("source_type", self._source_type)
        self._source_path = metadata.get("source_path", self._source_path)

    def _on_prediction_from_worker(self, prediction: dict[str, Any], frame: Any, metadata: dict[str, Any]) -> None:
        self._handle_prediction_background(prediction, frame, metadata)

    def _handle_prediction_background(self, prediction: dict[str, Any], frame: Any, metadata: dict[str, Any]) -> None:
        decision = self.alert_service.evaluate_detection(
            prediction,
            frame,
            metadata.get("source_type", "unknown"),
            metadata.get("source_path", ""),
            metadata.get("camera_id"),
            metadata.get("camera_location"),
            metadata,
        )
        self.after(0, lambda: self._apply_prediction(prediction, frame, decision, metadata))

    def _apply_prediction(self, prediction: dict[str, Any], frame: Any, decision: dict[str, Any], metadata: dict[str, Any]) -> None:
        source_type = metadata.get("source_type", self._source_type)
        source_path = metadata.get("source_path", self._source_path)
        ai_interval = metadata.get("ai_interval", self.video_service.interval_label)
        threat_level = decision.get("threat_level", "LOW")

        if threat_level in {"DANGER", "HIGH", "CRITICAL", "WARNING"} and decision.get("severity") != "LOW":
            self.camera_panel.set_frame(draw_detection_overlay(frame, prediction, str(threat_level)))

        self.camera_panel.set_status(
            animal=prediction.get("label", "--"),
            confidence=float(prediction.get("confidence", 0.0)),
            threat_level=str(threat_level),
            ai_interval=ai_interval,
            source_type=source_type,
            stream_state="Monitoring video for dangerous wildlife intrusion..." if source_type == "video" else "active",
        )
        self.camera_panel.set_metrics(
            processing_time_ms=float(metadata.get("processing_time_ms", 0.0) or 0.0),
            alert_decision_time_ms=float(decision.get("alert_decision_time_ms", 0.0) or 0.0),
            detection_latency=str(metadata.get("detection_video_timestamp", "--")),
            playback_fps=float(metadata.get("playback_fps", 0.0) or 0.0),
        )

        reason = str(decision.get("reason", ""))
        if threat_level in {"DANGER", "HIGH", "CRITICAL", "WARNING"} and decision.get("severity") != "LOW":
            reason = f"{reason}\nLocation: detected in current frame. Bounding box requires detection model."
        self.threat_panel.update_threat(str(threat_level), reason)
        self.threat_panel.update_detection(prediction)
        self.threat_panel.update_camera_info(self.alert_service.config, source_type, source_path)
        self._refresh_alert_views()
        self.threat_panel.update_sms_status(self.notification_service.sms_status())

        if decision.get("alert_triggered") and decision.get("event"):
            self._show_alert_popup(decision["event"])

    def _on_video_progress_from_worker(self, progress: dict[str, Any]) -> None:
        self.after(0, lambda: self.camera_panel.set_progress(progress))

    def _on_camera_status_from_worker(self, metadata: dict[str, Any]) -> None:
        self.after(0, lambda: self.camera_panel.set_status(stream_state=str(metadata.get("message", ""))))

    def _on_error_from_worker(self, message: str) -> None:
        self.after(0, lambda: self._show_error(message))

    def _show_error(self, message: str) -> None:
        messagebox.showerror("Wildlife Alert System", message)

    def _show_alert_popup(self, event: dict[str, Any]) -> None:
        popup = ctk.CTkToplevel(self)
        popup.title("DANGER Alert")
        popup.geometry("480x330")
        popup.configure(fg_color=COLORS["surface"])
        popup.attributes("-topmost", True)
        popup.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            popup,
            text="DANGER ALERT",
            text_color=COLORS["critical"],
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="ew", padx=22, pady=(24, 8))

        notification_line = event.get("notification_summary") or event.get("notification_status") or "SMS status unavailable."
        body = ctk.CTkLabel(
            popup,
            text=(
                f"{event.get('animal', 'Unknown')} detected near "
                f"{event.get('camera_location', 'camera')}.\n"
                f"Confidence: {float(event.get('confidence', 0.0)):.1%}\n"
                f"Video time: {event.get('detection_video_timestamp', '--')}\n"
                f"Snapshot: {event.get('snapshot_path', '')}\n"
                f"{notification_line}"
            ),
            text_color=COLORS["text"],
            justify="left",
            wraplength=420,
        )
        body.grid(row=1, column=0, sticky="ew", padx=24, pady=8)

        close_button = ctk.CTkButton(
            popup,
            text="Acknowledge",
            command=popup.destroy,
            fg_color=COLORS["danger"],
            hover_color="#a93434",
            corner_radius=6,
        )
        close_button.grid(row=2, column=0, padx=24, pady=(10, 20))
        popup.after(12000, popup.destroy)

    def _refresh_alert_views(self) -> None:
        events = self.alert_service.load_events()
        recent = list(reversed(events[-6:]))
        self.alert_history_panel.update_events(recent, len(events))
        if hasattr(self, "evidence_panel"):
            self.evidence_panel.update_events(recent)

    def _on_close(self) -> None:
        self.camera_service.stop(wait=False)
        self.video_service.stop(wait=False, reset=False)
        self.clip_service.finalize_all()
        self.siren_service.stop()
        self.destroy()


def run_dashboard() -> None:
    app = Dashboard()
    app.mainloop()
