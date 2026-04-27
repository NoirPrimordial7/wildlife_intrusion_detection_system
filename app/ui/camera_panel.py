from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk
import numpy as np

from app.core.video_service import DETECTION_INTERVALS
from app.ui.theme import COLORS, threat_color
from app.utils.image_utils import frame_to_pil, resize_to_fit
from app.utils.time_utils import format_seconds


SPEED_VALUES = ["0.25x", "0.5x", "0.75x", "1x", "1.25x", "1.5x", "2x"]


class CameraPanel(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, video_callbacks: dict[str, Callable[..., None]]) -> None:
        super().__init__(master, fg_color=COLORS["app_bg"], corner_radius=0)
        self.video_callbacks = video_callbacks
        self._image: ctk.CTkImage | None = None
        self._updating_slider = False
        self.marker_frame: ctk.CTkFrame | None = None
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.preview_area = ctk.CTkFrame(self, fg_color=COLORS["preview_bg"], corner_radius=8)
        self.preview_area.grid(row=0, column=0, sticky="nsew", padx=18, pady=(18, 10))
        self.preview_area.grid_columnconfigure(0, weight=1)
        self.preview_area.grid_rowconfigure(0, weight=1)

        self.preview_label = ctk.CTkLabel(
            self.preview_area,
            text="Upload a video to start Video Intrusion Detection",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=20, weight="bold"),
            fg_color=COLORS["preview_bg"],
        )
        self.preview_label.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        self.status_box = ctk.CTkFrame(self.preview_area, fg_color="#151a22", corner_radius=6)
        self.status_box.place(relx=0.02, rely=0.03)

        self.detected_label = self._status_label("Detected: --", 0)
        self.confidence_label = self._status_label("Confidence: --", 1)
        self.threat_label = self._status_label("Threat: SAFE", 2, bold=True)
        self.processing_label = self._status_label("AI: --", 3)
        self.frame_label = self._status_label("Frame: --", 4)

        self.controls = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=8)
        self.controls.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 18))
        self.controls.grid_columnconfigure(9, weight=1)
        self._build_video_controls()
        self._build_bottom_status()
        self.show_video_controls(False)

    def _status_label(self, text: str, row: int, bold: bool = False) -> ctk.CTkLabel:
        label = ctk.CTkLabel(
            self.status_box,
            text=text,
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=12, weight="bold" if bold else "normal"),
            anchor="w",
        )
        label.grid(row=row, column=0, sticky="ew", padx=10, pady=(7 if row == 0 else 1, 7 if row == 4 else 1))
        return label

    def _build_video_controls(self) -> None:
        button_specs = [
            ("Start Detection", "start"),
            ("Pause", "pause"),
            ("Resume", "resume"),
            ("Stop", "stop"),
            ("Restart", "restart"),
            ("-5 sec", "backward"),
            ("+5 sec", "forward"),
        ]
        for column, (label, key) in enumerate(button_specs):
            button = ctk.CTkButton(
                self.controls,
                text=label,
                width=118 if key == "start" else 78,
                height=34,
                corner_radius=6,
                fg_color=COLORS["surface_alt"],
                hover_color=COLORS["accent_hover"],
                command=self.video_callbacks.get(key),
            )
            button.grid(row=0, column=column, padx=(10 if column == 0 else 4, 4), pady=10)

        self.speed_menu = ctk.CTkOptionMenu(
            self.controls,
            values=SPEED_VALUES,
            width=92,
            command=self._on_speed_change,
        )
        self.speed_menu.set("1x")
        self.speed_menu.grid(row=0, column=7, padx=(10, 4), pady=10)

        self.interval_menu = ctk.CTkOptionMenu(
            self.controls,
            values=list(DETECTION_INTERVALS.keys()),
            width=140,
            command=self._on_interval_change,
        )
        self.interval_menu.set("Every 16 frames")
        self.interval_menu.grid(row=0, column=8, padx=4, pady=10)

        self.time_label = ctk.CTkLabel(
            self.controls,
            text="00:00 / 00:00 | Frame 0/0",
            text_color=COLORS["muted"],
            anchor="e",
            font=ctk.CTkFont(size=12),
        )
        self.time_label.grid(row=0, column=9, sticky="e", padx=(8, 12), pady=10)

        self.timeline = ctk.CTkSlider(self.controls, from_=0, to=100, command=self._on_timeline_change)
        self.timeline.set(0)
        self.timeline.grid(row=1, column=0, columnspan=10, sticky="ew", padx=12, pady=(0, 12))

        self.marker_frame = ctk.CTkFrame(self.controls, fg_color="transparent")
        self.marker_frame.grid(row=2, column=0, columnspan=10, sticky="ew", padx=12, pady=(0, 10))
        self.marker_frame.grid_columnconfigure(tuple(range(12)), weight=1)

    def _build_bottom_status(self) -> None:
        self.bottom_status = ctk.CTkFrame(self.preview_area, fg_color="#151a22", corner_radius=6)
        self.bottom_status.place(relx=0.015, rely=0.94, relwidth=0.97, anchor="sw")
        self.bottom_status.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        self.mode_label = self._bottom_label(0, "Mode: Hybrid YOLO + Classifier")
        self.monitoring_label = self._bottom_label(1, "AI Monitoring: idle")
        self.next_check_label = self._bottom_label(2, "Next: --")
        self.fps_label = self._bottom_label(3, "FPS: --")
        self.sms_label = self._bottom_label(4, "SMS: Disabled")
        self.cooldown_label = self._bottom_label(5, "Cooldown: --")

    def _bottom_label(self, column: int, text: str) -> ctk.CTkLabel:
        label = ctk.CTkLabel(self.bottom_status, text=text, text_color=COLORS["muted"], font=ctk.CTkFont(size=12), anchor="w")
        label.grid(row=0, column=column, sticky="ew", padx=8, pady=6)
        return label

    def _on_speed_change(self, value: str) -> None:
        numeric = float(value.replace("x", ""))
        callback = self.video_callbacks.get("speed")
        if callback:
            callback(numeric)

    def _on_interval_change(self, value: str) -> None:
        callback = self.video_callbacks.get("interval")
        if callback:
            callback(value)
        self.next_check_label.configure(text=f"Next: {value}")

    def _on_timeline_change(self, value: float) -> None:
        if self._updating_slider:
            return
        callback = self.video_callbacks.get("seek_percent")
        if callback:
            callback(value)

    def show_video_controls(self, show: bool) -> None:
        if show:
            self.controls.grid()
        else:
            self.controls.grid_remove()

    def set_frame(self, frame: np.ndarray) -> None:
        width = self.preview_label.winfo_width()
        height = self.preview_label.winfo_height()
        if width < 20 or height < 20:
            width, height = 880, 560
        image = resize_to_fit(frame_to_pil(frame), width, height)
        self._image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        self.preview_label.configure(image=self._image, text="")

    def set_status(
        self,
        animal: str | None = None,
        confidence: float | None = None,
        threat_level: str | None = None,
        ai_interval: str | None = None,
        source_type: str | None = None,
        stream_state: str | None = None,
    ) -> None:
        if animal is not None:
            self.detected_label.configure(text=f"Detected: {animal}")
        if confidence is not None:
            self.confidence_label.configure(text=f"Confidence: {confidence:.1%}")
        if threat_level is not None:
            self.threat_label.configure(
                text=f"Threat: {threat_level}",
                text_color=threat_color(threat_level),
            )
        if ai_interval is not None:
            pass
        if source_type is not None:
            pass
        if stream_state is not None:
            self.monitoring_label.configure(text=f"AI Monitoring: {stream_state}")

    def set_metrics(
        self,
        processing_time_ms: float | None = None,
        alert_decision_time_ms: float | None = None,
        detection_latency: str | None = None,
        playback_fps: float | None = None,
    ) -> None:
        if processing_time_ms is not None:
            self.processing_label.configure(text=f"AI: {processing_time_ms:.0f} ms")
        if detection_latency is not None:
            pass
        if playback_fps is not None:
            self.fps_label.configure(text=f"FPS: {playback_fps:.1f}")

    def set_monitoring_status(self, monitoring_state: str = "", next_check_in: str = "", last_checked_frame: str = "", last_checked_time: str = "", sms_status: str = "Disabled", cooldown_remaining: str = "--") -> None:
        if monitoring_state:
            self.monitoring_label.configure(text=monitoring_state)
        if next_check_in:
            self.next_check_label.configure(text=f"Next: {next_check_in}")
        if last_checked_frame or last_checked_time:
            self.frame_label.configure(text=f"Frame: {last_checked_frame} @ {last_checked_time}")
        self.sms_label.configure(text=f"SMS: {sms_status}")
        self.cooldown_label.configure(text=f"Cooldown: {cooldown_remaining}")

    def set_progress(self, progress: dict[str, Any]) -> None:
        current = format_seconds(progress.get("current_second", 0))
        duration = format_seconds(progress.get("duration_seconds", 0))
        frame_index = int(progress.get("frame_index", 0))
        frame_count = int(progress.get("frame_count", 0))
        self.time_label.configure(text=f"{current} / {duration} | Frame {frame_index}/{frame_count}")
        if progress.get("playback_fps") is not None:
            self.set_metrics(playback_fps=float(progress.get("playback_fps", 0.0)))
        self.set_monitoring_status(
            monitoring_state="AI Monitoring Active",
            next_check_in=str(progress.get("next_check_in", "--")),
            last_checked_frame=str(progress.get("last_checked_frame", "--")),
            last_checked_time=str(progress.get("last_checked_time", "--")),
        )
        self._updating_slider = True
        self.timeline.set(float(progress.get("percent", 0.0)))
        self._updating_slider = False

    def set_timeline_markers(self, markers: list[dict[str, Any]], on_click: Callable[[int], None]) -> None:
        if self.marker_frame is None:
            return
        for child in self.marker_frame.winfo_children():
            child.destroy()
        recent = markers[-12:]
        if not recent:
            return
        for index, marker in enumerate(recent):
            level = str(marker.get("level", "LOW")).upper()
            color = threat_color("DANGER" if level == "DANGER" else "WARNING" if level == "WARNING" else "LOW")
            frame_number = int(marker.get("frame", 0) or 0)
            button = ctk.CTkButton(
                self.marker_frame,
                text="",
                width=18,
                height=18,
                corner_radius=9,
                fg_color=color,
                hover_color=color,
                command=lambda value=frame_number: on_click(value),
            )
            tooltip = (
                f"Time: {marker.get('time', '--')}\n"
                f"Animal: {marker.get('animal', '--')}\n"
                f"Confidence: {float(marker.get('confidence', 0.0) or 0.0):.0%}"
            )
            button.bind("<Enter>", lambda _event, text=tooltip: self.time_label.configure(text=text.replace("\n", " | ")))
            button.grid(row=0, column=index, padx=3, pady=2)
