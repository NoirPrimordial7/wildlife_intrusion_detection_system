from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from app.ui.theme import COLORS, threat_color


OpenFileCallback = Callable[[str], None]


class AlertHistoryPanel(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, on_open_file: OpenFileCallback | None = None) -> None:
        super().__init__(master, fg_color=COLORS["surface"], corner_radius=8)
        self.on_open_file = on_open_file
        self.grid_columnconfigure(0, weight=1)
        self.rows_frame: ctk.CTkFrame | None = None
        self._build()

    def _build(self) -> None:
        title = ctk.CTkLabel(
            self,
            text="Live Alert Feed",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))

        self.counter_label = ctk.CTkLabel(
            self,
            text="Alerts: 0",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self.counter_label.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 2))

        self.last_label = ctk.CTkLabel(
            self,
            text="Last alert: --",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=12),
            anchor="w",
            wraplength=310,
        )
        self.last_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 10))

        self.rows_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.rows_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.rows_frame.grid_columnconfigure(0, weight=1)

    def update_events(self, events: list[dict[str, Any]], total_count: int | None = None) -> None:
        total = len(events) if total_count is None else total_count
        self.counter_label.configure(text=f"Alerts: {total}")
        self.last_label.configure(text=f"Last alert: {events[0].get('timestamp', '--')}" if events else "Last alert: --")

        if self.rows_frame is None:
            return
        for child in self.rows_frame.winfo_children():
            child.destroy()

        if not events:
            empty = ctk.CTkLabel(
                self.rows_frame,
                text="No alert events yet",
                text_color=COLORS["muted"],
                font=ctk.CTkFont(size=12),
                anchor="w",
            )
            empty.grid(row=0, column=0, sticky="ew", padx=4, pady=6)
            return

        for index, event in enumerate(events[:5]):
            self._event_row(index, event)

    def _event_row(self, row: int, event: dict[str, Any]) -> None:
        severity = str(event.get("severity") or event.get("threat_level") or "WARNING").upper()
        frame = ctk.CTkFrame(self.rows_frame, fg_color=COLORS["surface_alt"], corner_radius=6)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        frame.grid_columnconfigure(0, weight=1)

        text = (
            f"{event.get('detection_video_timestamp', '--')} | {event.get('animal', 'Unknown')} - {float(event.get('confidence', 0.0)):.1%}\n"
            f"notification {event.get('notification_status', '--')}\n"
            f"{event.get('timestamp', '')}"
        )
        label = ctk.CTkLabel(
            frame,
            text=text,
            text_color=threat_color(severity),
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
            justify="left",
            wraplength=270,
        )
        label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 4))

        snapshot = str(event.get("snapshot_path", "") or "")
        clip = str(event.get("clip_path", "") or "")
        self._file_button(frame, 1, 0, "Open Snapshot", snapshot)
        self._file_button(frame, 1, 1, "Open Clip", clip)

    def _file_button(self, parent: ctk.CTkFrame, row: int, column: int, text: str, path: str) -> None:
        button = ctk.CTkButton(
            parent,
            text=text,
            width=128,
            height=28,
            corner_radius=6,
            fg_color=COLORS["accent"] if path else COLORS["border"],
            hover_color=COLORS["accent_hover"],
            state="normal" if path else "disabled",
            command=lambda value=path: self._open_file(value),
        )
        button.grid(row=row, column=column, sticky="ew", padx=(10 if column == 0 else 4, 10), pady=(2, 10))

    def _open_file(self, path: str) -> None:
        if path and self.on_open_file:
            self.on_open_file(path)
