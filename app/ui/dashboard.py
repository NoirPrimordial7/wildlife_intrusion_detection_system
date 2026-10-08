from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk

from app.core.demo_service import DemoService
from app.core.alert_service import AlertService
from app.core.camera_service import CameraService
from app.core.clip_service import ClipService
from app.core.detection_localizer import draw_detection_overlay
from app.core.hybrid_detector import HybridDetector
from app.core.notification_service import NotificationService
from app.core.prediction_service import PredictionService
from app.core.report_service import ReportService
from app.core.siren_service import SirenService
from app.core.snapshot_service import SnapshotService
from app.core.video_service import VideoService
from app.ui.alert_history_panel import AlertHistoryPanel
from app.ui.camera_panel import CameraPanel
from app.ui.evidence_panel import EvidencePanel
from app.ui.notification_log_panel import NotificationLogPanel
from app.ui.settings_panel import SettingsPanel
from app.ui.sidebar import Sidebar
from app.ui.theme import COLORS
from app.ui.threat_panel import ThreatPanel
from app.utils.image_utils import load_image_as_bgr
from app.utils.paths import ALERTS_DIR, PROJECT_ROOT, TEST_VIDEOS_DIR, ensure_project_dirs


class Dashboard(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ensure_project_dirs()

        self.title("VanRakshak AI Wildlife Monitoring System")
        self.geometry("1360x840")
        self.minsize(1120, 700)
        self.configure(fg_color=COLORS["app_bg"])

        self.prediction_service = PredictionService()
        self.detector_service = HybridDetector(self.prediction_service)
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
            self.detector_service,
            self._on_frame_from_worker,
            self._on_prediction_from_worker,
            self._on_error_from_worker,
            self._on_camera_status_from_worker,
        )
        self.video_service = VideoService(
            self.detector_service,
            self._on_frame_from_worker,
            self._on_prediction_from_worker,
            self._on_video_progress_from_worker,
            self._on_error_from_worker,
        )

        self._source_type = "idle"
        self._source_path = ""
        self._last_stable_prediction: dict[str, Any] | None = None
        self._last_decision: dict[str, Any] | None = None
        self._timeline_markers: list[dict[str, Any]] = []
        self._danger_flash: ctk.CTkFrame | None = None
        self._closing = False
        self._ui_queue = queue.SimpleQueue()
        self._pending_frame = None
        self._frame_lock = threading.Lock()
        self._session = 0
        self.demo_service = DemoService(self._on_frame_from_worker, self._on_prediction_from_worker, self._on_video_progress_from_worker)
        self._build_layout()
        self.after(30, self._drain_ui_queue)
        self._refresh_static_state()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, minsize=208, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, minsize=360, weight=0)
        self.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=1, columnspan=2, sticky="ew", padx=20, pady=(18, 0))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="The field, in focus.", text_color=COLORS["text"],
                     font=ctk.CTkFont(size=27, weight="bold"), anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="Observe wildlife. Confirm the risk. Keep the evidence.",
                     text_color=COLORS["muted"], font=ctk.CTkFont(size=12), anchor="w").grid(row=1, column=0, sticky="w", pady=(2, 8))
        self.session_badge = ctk.CTkLabel(header, text="READY / LOCAL AI", corner_radius=8, fg_color=COLORS["surface_alt"],
                                         text_color=COLORS["accent"], width=150, height=32, font=ctk.CTkFont(size=11, weight="bold"))
        self.session_badge.grid(row=0, column=1, rowspan=2, padx=(12, 0))

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
                "quick_demo": self.quick_demo,
                "overview": lambda: self.inspector.set("Overview"),
                "evidence": lambda: self.inspector.set("Evidence"),
                "notifications": lambda: self.inspector.set("Messages"),
            },
        )
        self.sidebar.grid(row=0, rowspan=2, column=0, sticky="nsw")

        self.camera_panel = CameraPanel(
            self,
            {
                "start": self.video_start,
                "pause": self.video_pause,
                "resume": self.video_resume,
                "stop": self.video_stop,
                "restart": self.video_restart,
                "backward": lambda: self._playback.seek_seconds(-5),
                "forward": lambda: self._playback.seek_seconds(5),
                "speed": lambda value: self._playback.set_speed(value),
                "interval": lambda value: self._playback.set_detection_interval(value),
                "seek_percent": lambda value: self._playback.seek_percent(value),
            },
        )
        self.camera_panel.grid(row=1, column=1, sticky="nsew")

        self.inspector = ctk.CTkTabview(self, width=360, fg_color=COLORS["app_bg"],
                                       segmented_button_fg_color=COLORS["surface"],
                                       segmented_button_selected_color=COLORS["surface_alt"],
                                       segmented_button_selected_hover_color=COLORS["border"],
                                       segmented_button_unselected_color=COLORS["surface"],
                                       segmented_button_unselected_hover_color=COLORS["border"])
        self.inspector.grid(row=1, column=2, sticky="nsew", padx=(0, 14), pady=(0, 14))
        self.tab_panels = {}
        for name in ("Overview", "Evidence", "Messages", "Settings"):
            tab = self.inspector.add(name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
            panel = ctk.CTkScrollableFrame(tab, width=330, fg_color=COLORS["app_bg"], corner_radius=0)
            panel.grid(row=0, column=0, sticky="nsew")
            panel.grid_columnconfigure(0, weight=1)
            self.tab_panels[name] = panel
        self.right_panel = self.tab_panels["Overview"]

        self.threat_panel = ThreatPanel(self.right_panel)
        self.threat_panel.grid(row=0, column=0, sticky="ew")

        self.evidence_panel = EvidencePanel(
            self.tab_panels["Evidence"],
            self.open_project_file,
            self.export_report,
            self.focus_settings,
            self.acknowledge_alert,
        )
        self.evidence_panel.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        self.alert_history_panel = AlertHistoryPanel(self.tab_panels["Evidence"], self.open_project_file)
        self.alert_history_panel.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self.settings_panel = SettingsPanel(
            self.tab_panels["Settings"],
            self.alert_service.config,
            self.save_settings,
            self.stop_alarm,
            self.notification_service.users_with_last_status(),
            self.save_registered_users,
            self.test_sms_user,
            self.notification_service.load_sms_config(),
            self.save_sms_config,
            self.refresh_notification_views,
        )
        self.settings_panel.on_test_call = self.test_call_user
        self.settings_panel.grid(row=0, column=0, sticky="ew")

        self.notification_log_panel = NotificationLogPanel(
            self.tab_panels["Messages"],
            self.clear_notification_log,
            self.export_notification_log,
        )
        self.notification_log_panel.grid(row=0, column=0, sticky="ew", pady=(0, 12))

    @property
    def _playback(self):
        return self.demo_service if self._source_type == "demo" else self.video_service

    def _post_ui(self, callback):
        if not self._closing:
            self._ui_queue.put(callback)

    def _drain_ui_queue(self):
        if self._closing:
            return
        for _ in range(40):
            try:
                callback = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            callback()
        with self._frame_lock:
            pending, self._pending_frame = self._pending_frame, None
        if pending is not None:
            frame, metadata = pending
            if self._metadata_is_current(metadata):
                self._apply_frame(frame, metadata)
        self.after(30, self._drain_ui_queue)

    def _metadata_is_current(self, metadata):
        return (not self._closing and metadata.get("session", self._session) == self._session
                and metadata.get("source_type") == self._source_type
                and os.path.normcase(os.path.normpath(str(metadata.get("source_path", "")))) == os.path.normcase(os.path.normpath(self._source_path)))

    def _style_actions(self, parent):
        for child in parent.winfo_children():
            if isinstance(child, ctk.CTkButton) and child.cget("fg_color") == COLORS["accent"]:
                child.configure(text_color=COLORS["accent_text"])
            self._style_actions(child)

    def _refresh_static_state(self) -> None:
        self._style_actions(self)
        config = self.alert_service.config
        self.threat_panel.update_camera_info(config, self._source_type, self._source_path)
        self.threat_panel.update_sms_status(self.notification_service.sms_status())
        self._refresh_alert_views()
        self.camera_panel.set_status(
            animal="--",
            confidence=0.0,
            threat_level="LOW",
            ai_interval=self.video_service.interval_label,
            source_type="idle",
            stream_state="Ready / select a source",
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
        self._timeline_markers = []
        self.camera_panel.set_timeline_markers([], self.video_service.seek_frame)
        self.video_service.session = self._session
        self.session_badge.configure(text="VIDEO / READY")
        self.inspector.set("Overview")
        self.camera_panel.interval_menu.set(self.video_service.interval_label)
        self.camera_panel.speed_menu.set(f"{self.video_service.speed:g}x")
        if not self.video_service.open_video(path):
            self.stop_monitoring()

    def quick_demo(self) -> None:
        self.stop_monitoring(reset_status=False)
        self._source_type = "demo"
        self._source_path = "built-in simulation"
        self._timeline_markers = []
        self.camera_panel.show_video_controls(True)
        self.camera_panel.interval_menu.set(self.demo_service.interval_label)
        self.camera_panel.speed_menu.set("1x")
        self.camera_panel.set_timeline_markers([], self.demo_service.seek_frame)
        self.session_badge.configure(text="DEMO / SIMULATION")
        self.inspector.set("Overview")
        self.threat_panel.update_camera_info(self.alert_service.config, "demo", self._source_path)
        self.camera_panel.set_status(animal="--", confidence=0, threat_level="LOW", source_type="demo", stream_state="Guided simulation / no SMS sent")
        self.demo_service.speed = 1.0
        self.demo_service.session = self._session
        self.demo_service.restart()

    def video_start(self) -> None:
        self.camera_service.stop(wait=False)
        self.camera_panel.set_status(stream_state="Monitoring video for dangerous wildlife intrusion...")
        self.threat_panel.update_threat("LOW", "Monitoring video for dangerous wildlife intrusion...")
        self._playback.start()

    def video_pause(self) -> None:
        self._playback.pause()
        self.camera_panel.set_status(stream_state="Detection paused")

    def video_resume(self) -> None:
        self.camera_panel.set_status(stream_state="Monitoring video for dangerous wildlife intrusion...")
        self._playback.resume()

    def video_stop(self) -> None:
        self._playback.stop(wait=True, reset=True)
        self.clip_service.finalize_camera(self.alert_service.config.get("camera_id", "CAM_01"))
        self._last_stable_prediction = None
        self._last_decision = None
        self.camera_panel.set_status(animal="--", confidence=0, threat_level="LOW", source_type=self._source_type, stream_state="Detection stopped")
        self.threat_panel.update_threat("LOW", "Detection stopped")

    def video_restart(self) -> None:
        self.camera_panel.set_status(stream_state="Monitoring video for dangerous wildlife intrusion...")
        self._playback.restart()

    def start_webcam_monitoring(self) -> None:
        self.stop_monitoring(reset_status=False)
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
        self.session_badge.configure(text="WEBCAM / MONITORING")
        self.threat_panel.update_camera_info(self.alert_service.config, "webcam", "camera:0")
        self.camera_service.start_camera_stream("webcam", 0, 1.0, {"session": self._session})

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
        self.session_badge.configure(text="IMAGE / ANALYZING")
        self.inspector.set("Overview")
        threading.Thread(target=self._predict_image_worker, args=(frame, path, self._session), daemon=True).start()

    def stop_monitoring(self, reset_status: bool = True) -> None:
        self._session += 1
        self.demo_service.stop(wait=True, reset=False)
        self.camera_service.stop(wait=False)
        self.video_service.stop(wait=False, reset=False)
        self.clip_service.finalize_all()
        self._last_stable_prediction = None
        self._last_decision = None
        if reset_status:
            self._source_type = "idle"
            self._source_path = ""
            self.session_badge.configure(text="READY / LOCAL AI")
            self.camera_panel.show_video_controls(False)
            self.camera_panel.clear_frame()
            self.camera_panel.set_status(animal="--", confidence=0, threat_level="LOW", ai_interval=self.video_service.interval_label, source_type="idle", stream_state="Stopped")
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
        if not str(path):
            self._show_error("No evidence file is available yet.")
            return
        target = Path(path)
        if not target.is_absolute():
            target = PROJECT_ROOT / target
        if not target.exists():
            self._show_error(f"File is no longer available: {target}")
            return
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
        self.inspector.set("Settings")
        self.tab_panels["Settings"]._parent_canvas.yview_moveto(0)
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

    def save_sms_config(self, updates: dict[str, Any]) -> None:
        try:
            self.notification_service.save_sms_config(updates)
            self.refresh_notification_views()
            messagebox.showinfo("SMS settings saved", "Notification settings updated.")
        except Exception as exc:
            self._show_error(f"SMS settings could not be saved: {exc}")

    def test_sms_user(self, user: dict[str, Any]) -> None:
        sms_config = self.notification_service.load_sms_config()
        if not sms_config.get("enabled"):
            messagebox.showinfo("SMS not active", "SMS is disabled for demo. Enable it in Settings after adding credentials.")
            self.refresh_notification_views()
            return
        def worker():
            try:
                result = self.notification_service.send_test_sms(user)
            except Exception as exc:
                result = {"status": "failed", "error": str(exc)}
            self._post_ui(lambda: self._show_sms_result(result))
        threading.Thread(target=worker, daemon=True).start()

    def test_call_user(self, user):
        def worker():
            try:
                result = self.notification_service.send_test_call(user)
            except Exception as exc:
                result = {"status": "failed", "error": str(exc), "channel": "voice"}
            self._post_ui(lambda: self._show_sms_result(result))
        threading.Thread(target=worker, daemon=True).start()

    def _show_sms_result(self, result):
        self.refresh_notification_views()
        status = result.get("status", "unknown")
        if status == "queued":
            messagebox.showinfo("Test call queued", "Twilio accepted the call request. Check the recipient phone. Queued does not mean answered.")
        elif status == "sent":
            messagebox.showinfo("Test SMS sent", "Provider accepted the test SMS. Check the recipient phone.")
        else:
            messagebox.showinfo("Test SMS result", f"Status: {status}\n{result.get('error', '')}")

    def stop_alarm(self) -> None:
        self.siren_service.stop()

    def acknowledge_alert(self) -> None:
        self.threat_panel.update_threat("WARNING", "Alert acknowledged. Continue watching the current detection.")
        self.siren_service.stop()

    def refresh_notification_views(self) -> None:
        self.threat_panel.update_sms_status(self.notification_service.sms_status())
        if hasattr(self, "settings_panel"):
            self.settings_panel.reload_sms_config(self.notification_service.load_sms_config())
        if hasattr(self, "notification_log_panel"):
            self.notification_log_panel.update_logs(self.notification_service.load_notification_log())

    def clear_notification_log(self) -> None:
        self.notification_service.clear_notification_log()
        self.refresh_notification_views()

    def export_notification_log(self) -> None:
        path = self.notification_service.export_notification_log()
        messagebox.showinfo("Notification log exported", f"Notification log saved to:\n{path}")

    def _predict_image_worker(self, frame: Any, path: str, session: int) -> None:
        try:
            started_at = time.perf_counter()
            prediction = self.detector_service.predict_frame(frame.copy())
            processing_time_ms = round((time.perf_counter() - started_at) * 1000, 2)
            metadata = {
                "session": session,
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
        if not self._metadata_is_current(metadata):
            return
        camera_id = str(metadata.get("camera_id") or self.alert_service.config.get("camera_id", "CAM_01"))
        if metadata.get("source_type") != "demo":
            self.clip_service.add_frame(camera_id, frame, metadata)
        with self._frame_lock:
            self._pending_frame = (frame, metadata)

    def _apply_frame(self, frame: Any, metadata: dict[str, Any]) -> None:
        if self._last_stable_prediction and self._last_stable_prediction.get("detections"):
            level = "DANGER" if self._last_decision and self._last_decision.get("threat_level") == "DANGER" else "WARNING"
            frame = draw_detection_overlay(frame, self._last_stable_prediction, level)
        self.camera_panel.set_frame(frame)
        self._source_type = metadata.get("source_type", self._source_type)
        self._source_path = metadata.get("source_path", self._source_path)

    def _on_prediction_from_worker(self, prediction: dict[str, Any], frame: Any, metadata: dict[str, Any]) -> None:
        self._handle_prediction_background(prediction, frame, metadata)

    def _handle_prediction_background(self, prediction: dict[str, Any], frame: Any, metadata: dict[str, Any]) -> None:
        if not self._metadata_is_current(metadata):
            return
        if metadata.get("source_type") == "demo":
            second = float(metadata.get("current_second", 0))
            level = "DANGER" if 5 <= second < 10 else "WARNING" if 3 <= second < 5 else "LOW"
            decision = {"threat_level": level, "severity": level, "alert_triggered": False,
                        "repeat_count": 3 if level == "DANGER" else 1 if level == "WARNING" else 0,
                        "reason": "SIMULATION / confirmed intrusion. Real monitoring saves evidence and can send SMS." if level == "DANGER" else "SIMULATION / wildlife approaching the village boundary." if level == "WARNING" else "SIMULATION / perimeter clear. No real alerts or SMS are created."}
            self._post_ui(lambda: self._apply_prediction(prediction, frame, decision, metadata) if self._metadata_is_current(metadata) else None)
            return
        decision = self.alert_service.evaluate_detection(
            prediction,
            frame,
            metadata.get("source_type", "unknown"),
            metadata.get("source_path", ""),
            metadata.get("camera_id"),
            metadata.get("camera_location"),
            metadata,
        )
        self._post_ui(lambda: self._apply_prediction(prediction, frame, decision, metadata) if self._metadata_is_current(metadata) else None)

    def _apply_prediction(self, prediction: dict[str, Any], frame: Any, decision: dict[str, Any], metadata: dict[str, Any]) -> None:
        source_type = metadata.get("source_type", self._source_type)
        source_path = metadata.get("source_path", self._source_path)
        ai_interval = metadata.get("ai_interval", self.video_service.interval_label)
        threat_level = decision.get("threat_level", "LOW")

        if prediction.get("detections") or (threat_level in {"DANGER", "HIGH", "CRITICAL", "WARNING"} and decision.get("severity") != "LOW"):
            self.camera_panel.set_frame(draw_detection_overlay(frame, prediction, str(threat_level)))
            if source_type in {"video", "demo"}:
                self._add_timeline_marker(metadata, str(threat_level), prediction)

        self.camera_panel.set_status(
            animal=prediction.get("display_label", prediction.get("label", "--")),
            confidence=float(prediction.get("confidence", 0.0)),
            threat_level=str(threat_level),
            ai_interval=ai_interval,
            source_type=source_type,
            stream_state="Guided simulation / no SMS" if source_type == "demo" else "Image analyzed" if source_type == "image" else "Monitoring active",
        )
        self.camera_panel.set_metrics(
            processing_time_ms=float(metadata.get("processing_time_ms", 0.0) or 0.0),
            alert_decision_time_ms=float(decision.get("alert_decision_time_ms", 0.0) or 0.0),
            detection_latency=str(metadata.get("detection_video_timestamp", "--")),
            playback_fps=float(metadata.get("playback_fps", 0.0) or 0.0),
        )

        self.session_badge.configure(text="DEMO / SIMULATION" if source_type == "demo" else "IMAGE / COMPLETE" if source_type == "image" else "MONITORING / LOCAL AI")
        reason = str(decision.get("reason", ""))
        if threat_level in {"DANGER", "HIGH", "CRITICAL", "WARNING"} and decision.get("severity") != "LOW":
            event = decision.get("event") or {}
            location_note = event.get("location_note", "Location: YOLO bounding box around detected animal." if prediction.get("bbox") else "Location: detected in current frame. Bounding box requires detection model.")
            reason = f"{reason}\n{location_note}"
        self.threat_panel.update_threat(
            str(threat_level),
            reason,
            int(decision.get("repeat_count", 0) or 0),
            int(self.alert_service.config.get("required_repeated_detections", 3)),
        )
        self.threat_panel.update_detection(prediction)
        if prediction.get("yolo_error"):
            self.threat_panel.mode_label.configure(text="Detection mode: classifier fallback / YOLO unavailable")
        else:
            self.threat_panel.mode_label.configure(text="Detection mode: scripted simulation" if source_type == "demo" else "Detection mode: Hybrid YOLO + Classifier")
        self.threat_panel.update_camera_info(self.alert_service.config, source_type, source_path)
        self._refresh_alert_views()
        self.threat_panel.update_sms_status(self.notification_service.sms_status())
        self._last_stable_prediction = prediction
        self._last_decision = decision
        self.camera_panel.set_monitoring_status(
            sms_status="Demo / blocked" if source_type == "demo" else "Enabled" if self.notification_service.sms_status().get("enabled") else "Disabled",
            cooldown_remaining=f"{self.alert_service.cooldown_remaining()} sec",
        )

        if decision.get("alert_triggered") and decision.get("event"):
            self._flash_danger()
            self._show_alert_popup(decision["event"])

    def _on_video_progress_from_worker(self, progress: dict[str, Any]) -> None:
        self._post_ui(lambda: self.camera_panel.set_progress(progress) if self._metadata_is_current(progress) else None)

    def _add_timeline_marker(self, metadata: dict[str, Any], level: str, prediction: dict[str, Any] | None = None) -> None:
        prediction = prediction or self._last_stable_prediction or {}
        self._timeline_markers.append(
            {
                "frame": int(metadata.get("detection_frame_number", metadata.get("frame_index", 0)) or 0),
                "level": level,
                "time": str(metadata.get("detection_video_timestamp", metadata.get("last_checked_time", "--"))),
                "animal": str(prediction.get("display_label", prediction.get("label", "--"))),
                "confidence": float(prediction.get("confidence", 0.0) or 0.0),
            }
        )
        self._timeline_markers = self._timeline_markers[-80:]
        self.camera_panel.set_timeline_markers(self._timeline_markers, self._playback.seek_frame)

    def _flash_danger(self, step: int = 0) -> None:
        if self._closing:
            return
        self.camera_panel.preview_area.configure(border_color=COLORS["critical"] if step % 2 == 0 and step < 6 else COLORS["border"], border_width=2 if step < 6 else 1)
        if step < 6:
            self.after(180, lambda: self._flash_danger(step + 1))

    def _on_camera_status_from_worker(self, metadata: dict[str, Any]) -> None:
        self._post_ui(lambda: self.camera_panel.set_status(stream_state=str(metadata.get("message", ""))) if self._metadata_is_current(metadata) else None)

    def _on_error_from_worker(self, message: str) -> None:
        self._post_ui(lambda: self._show_error(message))

    def _show_error(self, message: str) -> None:
        messagebox.showerror("Wildlife Alert System", message)

    def _show_alert_popup(self, event: dict[str, Any]) -> None:
        popup = ctk.CTkToplevel(self)
        popup.title("DANGER DETECTED")
        popup.geometry("540x390")
        popup.configure(fg_color=COLORS["surface"])
        popup.attributes("-topmost", True)
        popup.transient(self)
        popup.grab_set()
        popup.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            popup,
            text="DANGER DETECTED",
            text_color=COLORS["critical"],
            font=ctk.CTkFont(size=30, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 8))

        animal = event.get("animal", event.get("display_label", "Wildlife"))
        confidence = float(event.get("confidence", 0.0))
        video_time = event.get("detection_video_timestamp", "--")
        notification_line = event.get("notification_summary") or event.get("notification_status") or "SMS status unavailable."

        body = ctk.CTkLabel(
            popup,
            text=(
                f"Animal: {animal}\n"
                f"Confidence: {confidence:.0%}\n"
                f"Time: {video_time}\n\n"
                f"{event.get('message', '')}\n\n"
                f"SMS: {notification_line}\n"
                f"Calls: {event.get('call_status', 'disabled')}"
            ),
            text_color=COLORS["text"],
            justify="left",
            wraplength=470,
            font=ctk.CTkFont(size=15),
        )
        body.grid(row=1, column=0, sticky="ew", padx=28, pady=10)

        button_row = ctk.CTkFrame(popup, fg_color="transparent")
        button_row.grid(row=2, column=0, sticky="ew", padx=24, pady=(8, 24))
        button_row.grid_columnconfigure((0, 1, 2), weight=1)

        def close_and_acknowledge() -> None:
            self.acknowledge_alert()
            popup.destroy()

        ctk.CTkButton(
            button_row,
            text="Acknowledge",
            command=close_and_acknowledge,
            fg_color=COLORS["critical"],
            hover_color=COLORS["danger"],
            corner_radius=6,
        ).grid(row=0, column=0, sticky="ew", padx=5)
        ctk.CTkButton(
            button_row,
            text="Open Snapshot",
            command=lambda: self.open_project_file(event.get("snapshot_path", "")),
            fg_color=COLORS["surface_alt"],
            hover_color=COLORS["accent_hover"],
            corner_radius=6,
        ).grid(row=0, column=1, sticky="ew", padx=5)
        ctk.CTkButton(
            button_row,
            text="SMS Settings",
            command=lambda: (popup.destroy(), self.focus_settings()),
            fg_color=COLORS["accent"],
            text_color=COLORS["accent_text"],
            hover_color=COLORS["accent_hover"],
            corner_radius=6,
        ).grid(row=0, column=2, sticky="ew", padx=5)

        popup.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (popup.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (popup.winfo_height() // 2)
        popup.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        popup.after(
            12000,
            lambda: popup.destroy() if popup.winfo_exists() else None,
        )

    def _refresh_alert_views(self) -> None:
        events = self.alert_service.load_events()
        recent = list(reversed(events[-6:]))
        for event in recent:
            event["cooldown_remaining"] = self.alert_service.cooldown_remaining(str(event.get("camera_id", "CAM_01")))
        self.alert_history_panel.update_events(recent, len(events))
        if hasattr(self, "evidence_panel"):
            self.evidence_panel.update_events(recent)
        if hasattr(self, "notification_log_panel"):
            self.notification_log_panel.update_logs(self.notification_service.load_notification_log())

    def _on_close(self) -> None:
        self._closing = True
        self.demo_service.stop(wait=True, reset=False)
        self.camera_service.stop(wait=False)
        self.video_service.stop(wait=True, reset=False)
        self.clip_service.finalize_all()
        self.siren_service.stop()
        self.destroy()


def run_dashboard() -> None:
    app = Dashboard()
    app.mainloop()
