from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk

from app.core.alert_service import AlertService
from app.core.camera_service import CameraService
from app.core.notification_service import NotificationService
from app.core.prediction_service import PredictionService
from app.core.report_service import ReportService
from app.core.snapshot_service import SnapshotService
from app.core.video_service import VideoService
from app.ui.alert_history_panel import AlertHistoryPanel
from app.ui.camera_panel import CameraPanel
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

        self.title("AI Wildlife Intrusion Detection and Alert System")
        self.geometry("1400x850")
        self.minsize(1100, 700)
        self.configure(fg_color=COLORS["app_bg"])

        self.prediction_service = PredictionService()
        self.notification_service = NotificationService()
        self.snapshot_service = SnapshotService()
        self.alert_service = AlertService(self.snapshot_service, self.notification_service)
        self.report_service = ReportService()

        self.camera_service = CameraService(
            self.prediction_service,
            self._on_frame_from_worker,
            self._on_prediction_from_worker,
            self._on_error_from_worker,
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
        self.grid_columnconfigure(2, minsize=370, weight=0)
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

        self.right_panel = ctk.CTkScrollableFrame(self, width=370, fg_color=COLORS["app_bg"], corner_radius=0)
        self.right_panel.grid(row=0, column=2, sticky="nsew", padx=(0, 14), pady=14)
        self.right_panel.grid_columnconfigure(0, weight=1)

        self.threat_panel = ThreatPanel(self.right_panel)
        self.threat_panel.grid(row=0, column=0, sticky="ew")

        self.alert_history_panel = AlertHistoryPanel(self.right_panel)
        self.alert_history_panel.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self.settings_panel = SettingsPanel(self.right_panel, self.alert_service.config, self.save_settings)
        self.settings_panel.grid(row=2, column=0, sticky="ew")

    def _refresh_static_state(self) -> None:
        config = self.alert_service.config
        self.threat_panel.update_camera_info(config, self._source_type, self._source_path)
        self.alert_history_panel.update_events(self.alert_service.recent_events())
        self.camera_panel.set_status(
            animal="--",
            confidence=0.0,
            threat_level="SAFE",
            ai_interval="Every 1 sec",
            source_type="idle",
        )

    def start_webcam_monitoring(self) -> None:
        self.video_service.stop(wait=False, reset=False)
        self._source_type = "webcam"
        self._source_path = "camera:0"
        self.camera_panel.show_video_controls(False)
        self.camera_panel.set_status(ai_interval="Every 1 sec", source_type="webcam", threat_level="SAFE")
        self.threat_panel.update_camera_info(self.alert_service.config, self._source_type, self._source_path)
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
        self.camera_panel.set_status(animal="Predicting...", confidence=0.0, threat_level="SAFE", ai_interval="Single image", source_type="image")
        self.threat_panel.update_camera_info(self.alert_service.config, self._source_type, path)

        thread = threading.Thread(target=self._predict_image_worker, args=(frame, path), daemon=True)
        thread.start()

    def upload_video(self) -> None:
        path = filedialog.askopenfilename(
            title="Select CCTV demo video",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.webm"), ("All files", "*.*")],
        )
        if not path:
            return
        self.stop_monitoring(reset_status=False)
        self._source_type = "video"
        self._source_path = path
        self.camera_panel.show_video_controls(True)
        self.camera_panel.set_status(animal="--", confidence=0.0, threat_level="SAFE", ai_interval=self.video_service.interval_label, source_type="video")
        self.threat_panel.update_camera_info(self.alert_service.config, self._source_type, path)
        self.video_service.open_video(path)

    def stop_monitoring(self, reset_status: bool = True) -> None:
        self.camera_service.stop(wait=False)
        self.video_service.stop(wait=False, reset=False)
        if reset_status:
            self._source_type = "idle"
            self._source_path = ""
            self.camera_panel.set_status(threat_level="SAFE", ai_interval="Every 1 sec", source_type="idle")
            self.threat_panel.update_threat("SAFE", "Monitoring stopped")
            self.threat_panel.update_camera_info(self.alert_service.config, "idle", "")

    def video_start(self) -> None:
        self.video_service.start()

    def video_pause(self) -> None:
        self.video_service.pause()

    def video_resume(self) -> None:
        self.video_service.resume()

    def video_stop(self) -> None:
        self.video_service.stop(wait=False, reset=True)
        self.camera_panel.set_status(threat_level="SAFE", source_type="video")

    def video_restart(self) -> None:
        self.video_service.restart()

    def export_report(self) -> None:
        try:
            path = self.report_service.export_alert_report()
            messagebox.showinfo("Report exported", f"Report saved to:\n{path}")
        except Exception as exc:
            self._show_error(f"Report export failed: {exc}")

    def open_alerts_folder(self) -> None:
        ALERTS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(ALERTS_DIR))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(ALERTS_DIR)])
            else:
                subprocess.Popen(["xdg-open", str(ALERTS_DIR)])
        except Exception as exc:
            self._show_error(f"Could not open alerts folder: {exc}")

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

    def _predict_image_worker(self, frame: Any, path: str) -> None:
        try:
            prediction = self.prediction_service.predict_frame(frame.copy())
            metadata = {"source_type": "image", "source_path": path, "ai_interval": "Single image"}
            self._handle_prediction_background(prediction, frame.copy(), metadata)
        except Exception as exc:
            self._on_error_from_worker(f"Image prediction failed: {exc}")

    def _on_frame_from_worker(self, frame: Any, metadata: dict[str, Any]) -> None:
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
        )
        self.after(0, lambda: self._apply_prediction(prediction, decision, metadata))

    def _apply_prediction(self, prediction: dict[str, Any], decision: dict[str, Any], metadata: dict[str, Any]) -> None:
        source_type = metadata.get("source_type", self._source_type)
        source_path = metadata.get("source_path", self._source_path)
        ai_interval = metadata.get("ai_interval", "Every 1 sec" if source_type == "webcam" else "Single image")

        self.camera_panel.set_status(
            animal=prediction.get("label", "--"),
            confidence=float(prediction.get("confidence", 0.0)),
            threat_level=decision.get("threat_level", "SAFE"),
            ai_interval=ai_interval,
            source_type=source_type,
        )
        self.threat_panel.update_threat(decision.get("threat_level", "SAFE"), decision.get("reason", ""))
        self.threat_panel.update_detection(prediction)
        self.threat_panel.update_camera_info(self.alert_service.config, source_type, source_path)
        self.alert_history_panel.update_events(self.alert_service.recent_events())

        if decision.get("alert_triggered") and decision.get("event"):
            self._show_alert_popup(decision["event"])

    def _on_video_progress_from_worker(self, progress: dict[str, Any]) -> None:
        self.after(0, lambda: self.camera_panel.set_progress(progress))

    def _on_error_from_worker(self, message: str) -> None:
        self.after(0, lambda: self._show_error(message))

    def _show_error(self, message: str) -> None:
        messagebox.showerror("Wildlife Alert System", message)

    def _show_alert_popup(self, event: dict[str, Any]) -> None:
        popup = ctk.CTkToplevel(self)
        popup.title("Wildlife Danger Alert")
        popup.geometry("420x230")
        popup.configure(fg_color=COLORS["surface"])
        popup.attributes("-topmost", True)
        popup.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            popup,
            text="DANGER ALERT",
            text_color=COLORS["danger"],
            font=ctk.CTkFont(size=26, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="ew", padx=22, pady=(24, 8))

        body = ctk.CTkLabel(
            popup,
            text=(
                f"{event.get('animal', 'Unknown')} detected at "
                f"{event.get('camera_location', 'camera')}.\n"
                f"Confidence: {float(event.get('confidence', 0.0)):.1%}\n"
                f"Snapshot: {event.get('snapshot_path', '')}"
            ),
            text_color=COLORS["text"],
            justify="left",
            wraplength=360,
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

    def _on_close(self) -> None:
        self.camera_service.stop(wait=False)
        self.video_service.stop(wait=False, reset=False)
        self.destroy()


def run_dashboard() -> None:
    app = Dashboard()
    app.mainloop()

