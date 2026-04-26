from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import customtkinter as ctk
from PIL import Image

from app.ui.theme import COLORS, threat_color
from app.utils.paths import PROJECT_ROOT


OpenFileCallback = Callable[[str], None]


class EvidencePanel(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, on_open_file: OpenFileCallback | None = None) -> None:
        super().__init__(master, fg_color=COLORS["surface"], corner_radius=8)
        self.on_open_file = on_open_file
        self._snapshot_path = ""
        self._snapshot_image: ctk.CTkImage | None = None
        self.timeline_frame: ctk.CTkFrame | None = None
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self) -> None:
        title = ctk.CTkLabel(
            self,
            text="Video Evidence",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))

        self.snapshot_label = ctk.CTkLabel(
            self,
            text="No alert snapshot yet",
            text_color=COLORS["muted"],
            fg_color=COLORS["preview_bg"],
            corner_radius=6,
            height=130,
        )
        self.snapshot_label.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        self.open_snapshot_button = ctk.CTkButton(
            self,
            text="Open Snapshot",
            height=32,
            corner_radius=6,
            fg_color=COLORS["border"],
            hover_color=COLORS["accent_hover"],
            state="disabled",
            command=self._open_snapshot,
        )
        self.open_snapshot_button.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))

        timeline_title = ctk.CTkLabel(
            self,
            text="Alert Timeline",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        timeline_title.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 4))

        self.timeline_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.timeline_frame.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 14))
        self.timeline_frame.grid_columnconfigure(0, weight=1)

    def update_events(self, events: list[dict[str, Any]]) -> None:
        if events:
            self._set_snapshot(str(events[0].get("snapshot_path", "") or ""))
        self._render_timeline(events[:6])

    def _set_snapshot(self, snapshot_path: str) -> None:
        if not snapshot_path:
            return
        self._snapshot_path = snapshot_path
        path = Path(snapshot_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        try:
            image = Image.open(path).convert("RGB")
            image.thumbnail((310, 150))
            self._snapshot_image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
            self.snapshot_label.configure(image=self._snapshot_image, text="")
            self.open_snapshot_button.configure(state="normal", fg_color=COLORS["accent"])
        except Exception:
            self.snapshot_label.configure(text=snapshot_path, image=None)
            self.open_snapshot_button.configure(state="normal", fg_color=COLORS["accent"])

    def _render_timeline(self, events: list[dict[str, Any]]) -> None:
        if self.timeline_frame is None:
            return
        for child in self.timeline_frame.winfo_children():
            child.destroy()
        if not events:
            empty = ctk.CTkLabel(
                self.timeline_frame,
                text="No danger alerts in this session yet",
                text_color=COLORS["muted"],
                anchor="w",
                font=ctk.CTkFont(size=12),
            )
            empty.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
            return
        for index, event in enumerate(events):
            confidence = float(event.get("confidence", 0.0))
            status = event.get("notification_status", "--")
            video_time = event.get("detection_video_timestamp", "--")
            text = f"{video_time} | {event.get('animal', 'Unknown')} | {confidence:.0%} | notification {status}"
            label = ctk.CTkLabel(
                self.timeline_frame,
                text=text,
                text_color=threat_color(str(event.get("threat_level", "DANGER"))),
                anchor="w",
                justify="left",
                wraplength=310,
                font=ctk.CTkFont(size=12),
            )
            label.grid(row=index, column=0, sticky="ew", padx=4, pady=3)

    def _open_snapshot(self) -> None:
        if self._snapshot_path and self.on_open_file:
            self.on_open_file(self._snapshot_path)
