from __future__ import annotations
from typing import Any, Callable
import customtkinter as ctk
import numpy as np
from PIL import Image
from app.core.video_service import DETECTION_INTERVALS
from app.ui.theme import COLORS, threat_color
from app.utils.image_utils import frame_to_pil, resize_to_fit
from app.utils.time_utils import format_seconds

SPEED_VALUES = ["0.25x", "0.5x", "0.75x", "1x", "1.25x", "1.5x", "2x"]


class CameraPanel(ctk.CTkFrame):
    def __init__(self, master, video_callbacks: dict[str, Callable[..., None]]) -> None:
        super().__init__(master, fg_color=COLORS["app_bg"], corner_radius=0)
        self.video_callbacks = video_callbacks
        self._image = None
        self._last_frame = None
        self._resize_job = None
        self._updating_slider = False
        self._time_text = "00:00 / 00:00"
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        heading = ctk.CTkFrame(self, fg_color="transparent")
        heading.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        heading.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(heading, text="Observation feed", anchor="w", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=COLORS["text"]).grid(row=0, column=0, sticky="w")
        self.source_label = ctk.CTkLabel(heading, text="NO SOURCE", text_color=COLORS["accent"], font=ctk.CTkFont(size=11, weight="bold"))
        self.source_label.grid(row=0, column=1, sticky="e")
        self.preview_area = ctk.CTkFrame(self, fg_color=COLORS["preview_bg"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        self.preview_area.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 12))
        self.preview_area.grid_columnconfigure(0, weight=1)
        self.preview_area.grid_rowconfigure(0, weight=1)
        self.preview_label = ctk.CTkLabel(self.preview_area, text="YOUR WATCH STARTS HERE\n\nUpload a wildlife video or connect a webcam.\nTry Guided demo for a walkthrough.",
                                         text_color=COLORS["muted"], font=ctk.CTkFont(size=17), wraplength=420)
        self.preview_label.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.preview_label.bind("<Configure>", self._schedule_resize)
        self.status_box = ctk.CTkFrame(self.preview_area, fg_color=COLORS["surface"], corner_radius=10)
        self.status_box.place(relx=0.025, rely=0.03)
        self.detected_label = self._status_label("Detected: --", 0)
        self.confidence_label = self._status_label("Confidence: --", 1)
        self.threat_label = self._status_label("Threat: IDLE", 2, True)
        self.processing_label = self._status_label("AI: --", 3)
        self.frame_label = self._status_label("Frame: --", 4)
        self.controls = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=12)
        self.controls.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))
        self.controls.grid_columnconfigure(0, weight=1)
        buttons = ctk.CTkFrame(self.controls, fg_color="transparent")
        buttons.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        buttons.grid_columnconfigure(tuple(range(7)), weight=1)
        self.buttons = {}
        for column, (label, key) in enumerate([("Start", "start"), ("Pause", "pause"), ("Resume", "resume"), ("Stop", "stop"), ("Restart", "restart"), ("-5s", "backward"), ("+5s", "forward")]):
            primary = key == "start"
            button = ctk.CTkButton(buttons, text=label, width=48, height=34, corner_radius=7,
                                  fg_color=COLORS["accent"] if primary else COLORS["surface_alt"],
                                  text_color=COLORS["accent_text"] if primary else COLORS["text"],
                                  hover_color=COLORS["accent_hover"], command=self.video_callbacks.get(key))
            button.grid(row=0, column=column, sticky="ew", padx=3)
            self.buttons[key] = button
        options = ctk.CTkFrame(self.controls, fg_color="transparent")
        options.grid(row=1, column=0, sticky="ew", padx=13, pady=6)
        options.grid_columnconfigure(2, weight=1)
        self.speed_menu = ctk.CTkOptionMenu(options, values=SPEED_VALUES, width=80, command=self._on_speed_change)
        self.speed_menu.set("1x")
        self.speed_menu.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.interval_menu = ctk.CTkOptionMenu(options, values=list(DETECTION_INTERVALS), width=140, command=self._on_interval_change)
        self.interval_menu.set("Every 16 frames")
        self.interval_menu.grid(row=0, column=1, sticky="w")
        self.time_label = ctk.CTkLabel(options, text=self._time_text, anchor="e", font=ctk.CTkFont(size=11), text_color=COLORS["muted"])
        self.time_label.grid(row=0, column=2, sticky="ew", padx=(6, 0))
        self.timeline = ctk.CTkSlider(self.controls, from_=0, to=100, command=self._on_timeline_change)
        self.timeline.set(0)
        self.timeline.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 10))
        self.marker_frame = ctk.CTkFrame(self.controls, fg_color="transparent")
        self.marker_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.marker_frame.grid_columnconfigure(tuple(range(3)), weight=1)
        self.bottom_status = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=10)
        self.bottom_status.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 16))
        self.bottom_status.grid_columnconfigure((0, 1, 2), weight=1)
        self.mode_label = self._bottom_label(0, "Hybrid detection")
        self.monitoring_label = self._bottom_label(1, "Ready to monitor")
        self.next_check_label = self._bottom_label(2, "Interval: 16 frames")
        self.fps_label = self._bottom_label(3, "FPS: --")
        self.sms_label = self._bottom_label(4, "SMS: Disabled")
        self.cooldown_label = self._bottom_label(5, "Cooldown: --")
        self.show_video_controls(False)

    def _status_label(self, text, row, bold=False):
        label = ctk.CTkLabel(self.status_box, text=text, anchor="w", text_color=COLORS["text"], font=ctk.CTkFont(size=11, weight="bold" if bold else "normal"))
        label.grid(row=row, column=0, sticky="ew", padx=12, pady=(6 if row == 0 else 0, 6 if row == 4 else 0))
        return label

    def _bottom_label(self, index, text):
        label = ctk.CTkLabel(self.bottom_status, text=text, text_color=COLORS["muted"], font=ctk.CTkFont(size=11), anchor="w", justify="left", wraplength=170)
        label.grid(row=index // 3, column=index % 3, sticky="ew", padx=10, pady=5)
        return label

    def _on_speed_change(self, value):
        self.video_callbacks["speed"](float(value.replace("x", "")))

    def _on_interval_change(self, value):
        self.video_callbacks["interval"](value)
        self.next_check_label.configure(text=f"Interval: {value}")

    def _on_timeline_change(self, value):
        if not self._updating_slider:
            self.video_callbacks["seek_percent"](value)

    def show_video_controls(self, show):
        self.controls.grid() if show else self.controls.grid_remove()

    def _schedule_resize(self, _event):
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(100, self._redraw_frame)

    def _redraw_frame(self):
        self._resize_job = None
        if self._last_frame is not None:
            self.set_frame(self._last_frame)

    def clear_frame(self):
        self._last_frame = None
        # Keep a valid Tk image reference when clearing; CTk does not clear the
        # underlying label image when configure(image=None) is used.
        blank = Image.new("RGB", (1, 1), COLORS["preview_bg"])
        self._image = ctk.CTkImage(light_image=blank, dark_image=blank, size=(1, 1))
        self.preview_label.configure(image=self._image, text="YOUR WATCH STARTS HERE\n\nUpload a wildlife video or connect a webcam.\nTry Guided demo for a walkthrough.")

    def set_frame(self, frame: np.ndarray):
        self._last_frame = frame
        width = max(20, self.preview_label.winfo_width() - 16)
        height = max(20, self.preview_label.winfo_height() - 16)
        image = resize_to_fit(frame_to_pil(frame), width, height)
        self._image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        self.preview_label.configure(image=self._image, text="")

    def set_status(self, animal=None, confidence=None, threat_level=None, ai_interval=None, source_type=None, stream_state=None):
        if animal is not None:
            self.detected_label.configure(text=f"Detected: {animal}")
        if confidence is not None:
            self.confidence_label.configure(text=f"Confidence: {confidence:.1%}" if animal != "--" else "Confidence: --")
        if threat_level is not None:
            self.threat_label.configure(text=f"Threat: {threat_level}", text_color=threat_color(threat_level))
        if ai_interval is not None:
            self.next_check_label.configure(text=f"Interval: {ai_interval}")
        if source_type is not None:
            self.source_label.configure(text={"idle": "NO SOURCE", "webcam": "LIVE CAMERA", "image": "STILL IMAGE", "video": "VIDEO FILE", "demo": "SIMULATION"}.get(source_type, source_type.upper()))
        if stream_state is not None:
            self.monitoring_label.configure(text=stream_state)

    def set_metrics(self, processing_time_ms=None, alert_decision_time_ms=None, detection_latency=None, playback_fps=None):
        if processing_time_ms is not None:
            text = f"AI: {processing_time_ms:.0f} ms"
            if alert_decision_time_ms is not None:
                text += f" / decision: {alert_decision_time_ms:.0f} ms"
            self.processing_label.configure(text=text)
        if detection_latency is not None:
            self.frame_label.configure(text=f"Checked at: {detection_latency}")
        if playback_fps is not None:
            self.fps_label.configure(text=f"FPS: {playback_fps:.1f}")

    def set_monitoring_status(self, monitoring_state="", next_check_in="", last_checked_frame="", last_checked_time="", sms_status=None, cooldown_remaining=None):
        if monitoring_state:
            self.monitoring_label.configure(text=monitoring_state)
        if next_check_in:
            self.next_check_label.configure(text=f"Next: {next_check_in}")
        if last_checked_frame or last_checked_time:
            self.frame_label.configure(text=f"Frame: {last_checked_frame} @ {last_checked_time}")
        if sms_status is not None:
            self.sms_label.configure(text=f"SMS: {sms_status}")
        if cooldown_remaining is not None:
            self.cooldown_label.configure(text=f"Cooldown: {cooldown_remaining}")

    def set_progress(self, progress: dict[str, Any]):
        self._time_text = f"{format_seconds(progress.get('current_second', 0))} / {format_seconds(progress.get('duration_seconds', 0))}"
        self.time_label.configure(text=self._time_text)
        state = progress.get("state", "loaded")
        for key, button in self.buttons.items():
            enabled = (key == "pause" and state == "playing") or (key == "resume" and state == "paused") or (key == "start" and state in {"loaded", "stopped", "finished"}) or key in {"stop", "restart", "backward", "forward"}
            button.configure(state="normal" if enabled else "disabled")
        self.set_metrics(playback_fps=float(progress.get("playback_fps", 0)))
        self.set_monitoring_status(monitoring_state={"loaded": "Ready / press Start", "playing": "Monitoring active", "paused": "Paused", "stopped": "Stopped", "finished": "Complete / restart to replay"}.get(state, state),
                                   next_check_in=str(progress.get("next_check_in", "--")),
                                   last_checked_frame=str(progress.get("last_checked_frame", "--")), last_checked_time=str(progress.get("last_checked_time", "--")))
        self._updating_slider = True
        try:
            self.timeline.set(float(progress.get("percent", 0)))
        finally:
            self._updating_slider = False

    def set_timeline_markers(self, markers, on_click):
        for child in self.marker_frame.winfo_children():
            child.destroy()
        if not markers:
            ctk.CTkLabel(self.marker_frame, text="Detection bookmarks appear here. Click one to revisit.", text_color=COLORS["muted"], font=ctk.CTkFont(size=11), wraplength=380).grid(row=0, column=0, columnspan=3, sticky="w", padx=4)
        for index, marker in enumerate(markers[-6:]):
            color = threat_color(str(marker.get("level", "WARNING")))
            ctk.CTkButton(self.marker_frame, text=f"{marker.get('time', '--')} / {marker.get('animal', '--')}", width=70, height=25,
                          font=ctk.CTkFont(size=10), fg_color=COLORS["surface_alt"], text_color=color, hover_color=COLORS["border"],
                          command=lambda value=int(marker.get("frame", 0)): on_click(value)).grid(row=index // 3, column=index % 3, sticky="ew", padx=3, pady=3)
